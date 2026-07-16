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
    verify_password,
)
from infrastructure.api import fastapi_app as api
from database.student_repository import StudentRepository
from scripts.prepare_e2e_seed import rotate_existing_user


class E2ECredentialRotationTests(unittest.TestCase):
    class FakeRepository:
        def __init__(self, user: dict | None) -> None:
            self.user = user
            self.updated: tuple[str, str] | None = None

        def get_user_by_email(self, _email: str) -> dict | None:
            return self.user

        def update_password(self, user_id: str, password_hash: str) -> None:
            self.updated = (user_id, password_hash)

    def test_existing_e2e_password_is_replaced_with_a_hash(self) -> None:
        repo = self.FakeRepository({"user_id": "user_e2e"})

        rotated = rotate_existing_user(repo, "student.e2e@proctorai.local", "ephemeral-secret")

        self.assertTrue(rotated)
        self.assertIsNotNone(repo.updated)
        self.assertEqual(repo.updated[0], "user_e2e")
        self.assertTrue(verify_password("ephemeral-secret", repo.updated[1]))

    def test_missing_e2e_identity_is_not_created(self) -> None:
        repo = self.FakeRepository(None)

        rotated = rotate_existing_user(repo, "missing.e2e@proctorai.local", "ephemeral-secret")

        self.assertFalse(rotated)
        self.assertIsNone(repo.updated)


class BrowserActivityPersistenceTests(unittest.TestCase):
    class FakeDatabase:
        def __init__(self) -> None:
            self.executed: tuple[str, tuple] | None = None
            self.rows: list[dict] = []

        def execute(self, sql: str, params: tuple = ()) -> int:
            self.executed = (sql, params)
            return 1

        def query(self, _sql: str, _params: tuple = ()) -> list[dict]:
            return self.rows

    def test_repository_persists_full_browser_activity(self) -> None:
        db = self.FakeDatabase()
        repo = StudentRepository(db)

        repo.insert_browser_activity(
            "session_1",
            "tab_switch",
            "2026-07-16T10:00:00Z",
            url="https://example.test/answer",
            title="Example Answer",
            category="Search",
            risk_level="high",
            risk_points=10,
            source="browser_guard_extension",
            tenant_id="tenant_1",
        )

        self.assertIsNotNone(db.executed)
        self.assertIn("INSERT INTO BrowserActivity", db.executed[0])
        self.assertEqual(db.executed[1][0:3], ("tenant_1", "session_1", "tab_switch"))
        self.assertIn("https://example.test/answer", db.executed[1])
        self.assertIn("browser_guard_extension", db.executed[1])

    def test_repeated_activity_is_deduplicated_only_when_nearby(self) -> None:
        existing = [{
            "type": "tab_switch",
            "url": "https://example.test",
            "title": "Example",
            "timestamp": "2026-07-16T10:00:00Z",
        }]
        nearby = {**existing[0], "timestamp": "2026-07-16T10:00:01Z"}
        later = {**existing[0], "timestamp": "2026-07-16T10:05:00Z"}

        self.assertTrue(api._has_near_browser_row(existing, nearby))
        self.assertFalse(api._has_near_browser_row(existing, later))

    def test_persisted_row_normalizes_for_the_api(self) -> None:
        row = api._normalize_browser_activity({
            "activity_id": 7,
            "session_id": "session_1",
            "activity_type": "devtools",
            "url": "https://example.test",
            "title": "Developer tools",
            "category": "DevTools",
            "risk_level": "high",
            "risk_points": 12,
            "source": "browser_guard_extension",
            "event_time": "2026-07-16T10:00:00Z",
        })

        self.assertEqual(row["type"], "devtools")
        self.assertEqual(row["risk_impact"], 12)
        self.assertEqual(row["source"], "browser_guard_extension")
        self.assertEqual(row["time"], "10:00:00")


class PersistenceHonestyTests(unittest.TestCase):
    class ActiveDatabase:
        is_active = True

    def setUp(self) -> None:
        api._events.clear()
        api._browser_events.clear()
        api._session_meta.clear()
        api._session_store.clear()

    def test_ingest_key_is_stable_and_session_bound(self) -> None:
        first = api._ingest_key("session_1", "client-event-1", "risk_event")
        retry = api._ingest_key("session_1", "client-event-1", "risk_event")
        another_session = api._ingest_key("session_2", "client-event-1", "risk_event")

        self.assertEqual(first, retry)
        self.assertNotEqual(first, another_session)
        self.assertEqual(len(first), 64)

    def test_duplicate_event_is_acknowledged_without_memory_duplication(self) -> None:
        with (
            patch.object(api, "_get_db", return_value=self.ActiveDatabase()),
            patch.object(StudentRepository, "event_ingest_exists", return_value=True),
        ):
            result = api._persist_event(
                "session_1",
                "student_1",
                "Face Missing",
                8,
                "No face",
                {"ingest_id": "client-event-1"},
            )

        self.assertTrue(result["duplicate"])
        self.assertEqual(result["persistence"], "persisted")
        self.assertEqual(api._events, [])

    def test_failed_event_write_returns_503_without_phantom_event(self) -> None:
        with (
            patch.object(api, "_get_db", return_value=self.ActiveDatabase()),
            patch.object(StudentRepository, "event_ingest_exists", return_value=False),
            patch.object(StudentRepository, "upsert_session", side_effect=RuntimeError("write failed")),
        ):
            with self.assertRaises(api.HTTPException) as raised:
                api._persist_event(
                    "session_1",
                    "student_1",
                    "Face Missing",
                    8,
                    "No face",
                    {"ingest_id": "client-event-1"},
                )

        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(api._events, [])

    def test_duplicate_browser_activity_is_acknowledged_without_memory_duplication(self) -> None:
        with (
            patch.object(api, "_get_db", return_value=self.ActiveDatabase()),
            patch.object(StudentRepository, "browser_activity_ingest_exists", return_value=True),
        ):
            result = api._record_browser_activity(
                "tab_switch",
                session_id="session_1",
                risk="medium",
                ingest_id="client-browser-1",
            )

        self.assertTrue(result["duplicate"])
        self.assertEqual(result["persistence"], "persisted")
        self.assertEqual(api._browser_events, [])

    def test_failed_browser_write_returns_503_without_phantom_activity(self) -> None:
        with (
            patch.object(api, "_get_db", return_value=self.ActiveDatabase()),
            patch.object(StudentRepository, "browser_activity_ingest_exists", return_value=False),
            patch.object(StudentRepository, "insert_browser_activity", side_effect=RuntimeError("write failed")),
        ):
            with self.assertRaises(api.HTTPException) as raised:
                api._record_browser_activity(
                    "tab_switch",
                    session_id="session_1",
                    risk="medium",
                    ingest_id="client-browser-1",
                )

        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(api._browser_events, [])

    def test_failed_session_start_does_not_create_memory_state(self) -> None:
        with (
            patch.object(api, "_get_db", return_value=self.ActiveDatabase()),
            patch.object(StudentRepository, "upsert_session", side_effect=RuntimeError("write failed")),
        ):
            with self.assertRaises(api.HTTPException) as raised:
                api.start_session(
                    api.SessionMeta(session_id="session_fail", student_id="student_1"),
                    None,
                    {"user_id": "student_1", "role": "student", "tenant_id": "tenant_1"},
                )

        self.assertEqual(raised.exception.status_code, 503)
        self.assertNotIn("session_fail", api._session_store)
        self.assertEqual(api._session_meta, {})

    def test_proctor_retry_reuses_the_same_ingest_id(self) -> None:
        import run_proctor_engine

        class SuccessfulResponse:
            @staticmethod
            def raise_for_status() -> None:
                return None

            @staticmethod
            def json() -> dict:
                return {"persistence": "persisted", "duplicate": False}

        engine = object.__new__(run_proctor_engine.ProctorEngine)
        engine.session = {"session_id": "session_1", "student_id": "student_1"}
        engine.last_error = ""
        with (
            patch.object(
                run_proctor_engine.requests,
                "post",
                side_effect=[RuntimeError("temporary"), RuntimeError("temporary"), SuccessfulResponse()],
            ) as post,
            patch.object(run_proctor_engine.time, "sleep"),
        ):
            engine._post_event("Face Missing", "No face")

        ingest_ids = [call.kwargs["json"]["ingest_id"] for call in post.call_args_list]
        self.assertEqual(len(post.call_args_list), 3)
        self.assertEqual(len(set(ingest_ids)), 1)
        self.assertEqual(engine.last_error, "")


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

        with patch.object(
            api,
            "_persist_event",
            return_value={"persistence": "persisted", "duplicate": False},
        ) as persist:
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
