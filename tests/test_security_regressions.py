from __future__ import annotations

import os
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("AUTH_SECRET", "test-auth-secret-that-is-at-least-thirty-two-characters")

from config.settings import PROCTOR_DEVICE_SECRET
from core.security import (
    create_browser_guard_token,
    create_media_token,
    decode_browser_guard_token,
    decode_media_token,
)
from infrastructure.api import fastapi_app as api


class AnswerPrivacyTests(unittest.TestCase):
    def test_student_response_omits_grading_fields(self) -> None:
        response = {
            "response_id": "response_1",
            "attempt_id": "attempt_1",
            "question_id": "question_1",
            "selected_option_id": "option_correct",
            "response_text": "",
            "is_correct": True,
            "awarded_marks": 5,
        }

        public = api._format_attempt_response(response, include_grading=False)

        self.assertNotIn("is_correct", public)
        self.assertNotIn("awarded_marks", public)
        self.assertEqual(public["selected_option_id"], "option_correct")

    def test_instructor_response_includes_grading_fields(self) -> None:
        response = {
            "response_id": "response_1",
            "attempt_id": "attempt_1",
            "question_id": "question_1",
            "is_correct": True,
            "awarded_marks": 5,
        }

        private = api._format_attempt_response(response, include_grading=True)

        self.assertIs(private["is_correct"], True)
        self.assertEqual(private["awarded_marks"], 5)


class BrowserGuardTokenTests(unittest.TestCase):
    def test_token_is_session_bound_and_tamper_evident(self) -> None:
        token = create_browser_guard_token(
            {"user_id": "student_1", "tenant_id": "tenant_1"},
            "session_1",
        )

        claims = decode_browser_guard_token(token)

        self.assertEqual(claims["sub"], "student_1")
        self.assertEqual(claims["session_id"], "session_1")
        with self.assertRaises(ValueError):
            decode_browser_guard_token(f"{token[:-1]}{'A' if token[-1] != 'A' else 'B'}")

    def test_media_token_is_session_bound_and_tamper_evident(self) -> None:
        token = create_media_token({"user_id": "student_1", "tenant_id": "tenant_1"}, "session_1")
        claims = decode_media_token(token)
        self.assertEqual(claims["purpose"], "video_stream")
        self.assertEqual(claims["session_id"], "session_1")
        with self.assertRaises(ValueError):
            decode_media_token(f"{token[:-1]}{'A' if token[-1] != 'A' else 'B'}")

    def test_capture_path_cannot_escape_or_cross_sessions(self) -> None:
        with self.assertRaises(ValueError):
            api._resolve_session_capture("../secret.jpg", "session_1")
        with self.assertRaises(ValueError):
            api._resolve_session_capture("session_2/frame.jpg", "session_1")

    def test_video_feed_rejects_anonymous_requests(self) -> None:
        from monitoring.tab_switch_detector import TabSwitchDetector

        detector = TabSwitchDetector()
        with patch.object(TabSwitchDetector, "_run_flask", lambda _self: None):
            detector.start()
        response = detector._app.test_client().get("/video_feed")
        self.assertEqual(response.status_code, 401)


class ReportConsistencyTests(unittest.TestCase):
    def test_report_metadata_uses_capped_risk_and_real_timestamp(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            report_path = Path(temp_dir) / "session_1_report.pdf"
            report_path.write_bytes(b"%PDF-test")
            with patch.object(api, "_get_session_events", return_value=[{"risk_points": 80}, {"risk_points": 70}]):
                metadata = api._report_metadata("session_1", str(report_path))
        self.assertEqual(metadata["risk_score"], 100)
        self.assertEqual(metadata["risk_level"], "critical")
        self.assertTrue(metadata["generated_at"].endswith("Z"))
        self.assertNotIn("pdf_path", metadata)

    def test_pdf_evidence_timestamp_is_loaded_from_index(self) -> None:
        from config import settings
        from core.reporting.pdf_generator import PDFReportGenerator

        with tempfile.TemporaryDirectory() as temp_dir:
            session_dir = Path(temp_dir) / "session_1"
            session_dir.mkdir()
            image_path = session_dir / "frame.jpg"
            image_path.write_bytes(b"image")
            (session_dir / "evidence_index.json").write_text(
                json.dumps({
                    "evidence": [{
                        "filename": "frame.jpg",
                        "event_type": "Face Missing",
                        "timestamp": "2026-07-15T12:34:56+00:00",
                    }]
                }),
                encoding="utf-8",
            )
            with patch.object(settings, "SCREENSHOTS_DIR", temp_dir):
                evidence = PDFReportGenerator("session_1")._load_screenshots()
        self.assertEqual(evidence[0]["time"], "12:34:56")


@unittest.skipUnless(getattr(api, "_FASTAPI_AVAILABLE", False), "FastAPI is not installed")
class EndpointProtectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from fastapi.testclient import TestClient

        cls.client = TestClient(api.app)

    def setUp(self) -> None:
        api._events.clear()
        api._browser_events.clear()
        api._session_meta.clear()
        api._session_store.clear()

    def test_anonymous_ingestion_and_control_are_rejected(self) -> None:
        event = self.client.post(
            "/events",
            json={"session_id": "session_1", "student_id": "student_1", "event_type": "Face Missing"},
        )
        browser = self.client.post("/browser-events", json={"type": "heartbeat"})
        control = self.client.post("/proctor/start", json={"session_id": "session_1"})

        self.assertEqual(event.status_code, 401)
        self.assertEqual(browser.status_code, 401)
        self.assertEqual(control.status_code, 401)

        protected_requests = [
            ("get", "/browser-guard/ping", None),
            ("get", "/browser-guard/active", None),
            ("post", "/browser-guard/token", {"session_id": "session_1"}),
            ("post", "/keyboard-event", {"combo": "Ctrl+C"}),
            ("post", "/clipboard-event", {"action": "copy"}),
            ("post", "/tab-event", {"direction": "away"}),
            ("post", "/devtools-event", {"state": "open"}),
            ("post", "/fullscreen-event", {"state": "exit"}),
            ("post", "/proctor/stop", {}),
            ("get", "/proctor/status", None),
            ("get", "/captures/session_1/frame.jpg?session_id=session_1", None),
        ]
        for method, path, body in protected_requests:
            with self.subTest(path=path):
                response = self.client.request(method, path, json=body)
                self.assertEqual(response.status_code, 401)

    def test_authenticated_heartbeat_has_zero_risk_and_is_not_persisted(self) -> None:
        api._session_meta.update({"session_id": "session_1", "student_id": "student_1"})
        api._session_store["session_1"] = {
            "session_id": "session_1",
            "user_id": "student_1",
            "student_id": "student_1",
            "tenant_id": "tenant_1",
            "status": "Active",
        }

        response = self.client.post(
            "/browser-events",
            headers={"X-Proctor-Device-Secret": PROCTOR_DEVICE_SECRET},
            json={
                "type": "heartbeat",
                "source": "browser_guard_companion",
                "risk": "low",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIs(response.json()["scored"], False)
        self.assertEqual(api._events, [])
        self.assertEqual(api._browser_events, [])

    def test_trusted_sidecar_event_is_bound_to_active_session(self) -> None:
        api._session_meta.update({"session_id": "session_1", "student_id": "student_1"})
        api._session_store["session_1"] = {
            "session_id": "session_1",
            "user_id": "student_1",
            "student_id": "student_1",
            "tenant_id": "tenant_1",
            "status": "Active",
        }

        with patch.object(api, "_persist_event") as persist:
            response = self.client.post(
                "/events",
                headers={"X-Proctor-Device-Secret": PROCTOR_DEVICE_SECRET},
                json={
                    "session_id": "session_1",
                    "student_id": "forged_student",
                    "event_type": "Face Missing",
                    "risk_points": 99,
                    "notes": "No face visible",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(persist.call_args.args[1], "student_1")
        self.assertEqual(persist.call_args.args[3], 8)

    def test_trusted_sidecar_cannot_write_another_session(self) -> None:
        api._session_meta.update({"session_id": "session_1", "student_id": "student_1"})

        response = self.client.post(
            "/events",
            headers={"X-Proctor-Device-Secret": PROCTOR_DEVICE_SECRET},
            json={"session_id": "session_2", "event_type": "Face Missing"},
        )

        self.assertEqual(response.status_code, 409)


if __name__ == "__main__":
    unittest.main()
