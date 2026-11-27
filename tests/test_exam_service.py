from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

os.environ["AUTH_SECRET"] = os.environ.get("AUTH_SECRET") or (
    "test-auth-secret-that-is-at-least-thirty-two-characters"
)

from services.exam_service import (
    ExamService,
    ExamServiceError,
    format_exam,
    format_attempt_response,
    format_question,
)


class ActiveDatabase:
    is_active = True


def make_service(repository, **overrides) -> ExamService:
    values = {
        "repository_provider": lambda: repository,
        "database_provider": lambda: ActiveDatabase(),
        "get_active_session_id": lambda: "",
        "clear_active_session": lambda _session_id: None,
        "write_active_proctor_state": lambda *_args: None,
        "session_meta": {},
        "session_store": {},
        "get_session_events": lambda _session_id: [],
        "generate_report_file": lambda session_id: f"{session_id}.pdf",
        "report_metadata": lambda session_id, path: {
            "session_id": session_id,
            "path": path,
        },
        "reports_dir": tempfile.gettempdir(),
        "now": lambda: datetime(2026, 7, 16, 12, 0, tzinfo=timezone.utc),
        "session_id_factory": lambda: "session_generated",
    }
    values.update(overrides)
    return ExamService(**values)


class ExamValidationTests(unittest.TestCase):
    def test_exam_formatter_exposes_canonical_and_legacy_identifiers(self) -> None:
        formatted = format_exam({"exam_id": "exam_1", "title": "Exam"})

        self.assertEqual(formatted["id"], "exam_1")
        self.assertEqual(formatted["exam_id"], "exam_1")

    def test_exam_payload_is_normalized_and_schedule_is_validated(self) -> None:
        service = make_service(object())
        payload = service.validate_exam_payload(
            {
                "exam_code": " calc 101!* ",
                "title": "  Calculus  ",
                "description": "  Midterm  ",
                "semester": " Fall ",
                "subject": " Math ",
                "department": " Science ",
                "total_marks": 10,
                "duration_minutes": 30,
                "start_time": "2026-07-16T12:00:00+00:00",
                "end_time": "2026-07-16T13:00:00+00:00",
                "status": " DRAFT ",
                "rules": "No external material",
            }
        )

        self.assertEqual(payload["exam_code"], "CALC101")
        self.assertEqual(payload["title"], "Calculus")
        self.assertEqual(payload["status"], "draft")
        self.assertEqual(payload["rules"], {"policy": "No external material"})

        with self.assertRaises(ExamServiceError) as invalid:
            service.validate_exam_payload(
                {
                    **payload,
                    "start_time": "2026-07-16T14:00:00+00:00",
                    "end_time": "2026-07-16T13:00:00+00:00",
                }
            )
        self.assertEqual(invalid.exception.error, "validation_error")

    def test_question_and_response_privacy_is_role_sensitive(self) -> None:
        question = {
            "question_id": "question_1",
            "exam_id": "exam_1",
            "question_text": "Which answer is correct?",
            "options": [
                {
                    "option_id": "option_1",
                    "question_id": "question_1",
                    "option_text": "A",
                    "is_correct": True,
                }
            ],
        }
        response = {
            "response_id": "response_1",
            "attempt_id": "attempt_1",
            "question_id": "question_1",
            "is_correct": True,
            "awarded_marks": 2,
        }

        student_question = format_question(question, include_correct=False)
        student_response = format_attempt_response(response, include_grading=False)
        instructor_question = format_question(question, include_correct=True)
        instructor_response = format_attempt_response(response, include_grading=True)

        self.assertNotIn("is_correct", student_question["options"][0])
        self.assertNotIn("is_correct", student_response)
        self.assertNotIn("awarded_marks", student_response)
        self.assertTrue(instructor_question["options"][0]["is_correct"])
        self.assertEqual(instructor_response["awarded_marks"], 2)

    def test_exam_window_uses_the_injected_clock(self) -> None:
        service = make_service(object())
        with self.assertRaises(ExamServiceError) as not_started:
            service.require_exam_window(
                {
                    "start_time": "2026-07-16T12:01:00+00:00",
                    "end_time": "2026-07-16T13:00:00+00:00",
                }
            )
        self.assertEqual(not_started.exception.error, "exam_not_started")

        expired = {
            "started_at": datetime(2026, 7, 16, 11, 29, tzinfo=timezone.utc),
            "duration_minutes": 30,
        }
        self.assertTrue(service.attempt_expired(expired))


class AttemptConcurrencyTests(unittest.TestCase):
    def test_attempt_start_race_loser_returns_the_winner_as_a_conflict(self) -> None:
        class RaceRepository:
            def __init__(self) -> None:
                self.active_user_checks = 0

            def get_exam(self, _exam_id: str) -> dict:
                return {
                    "exam_id": "exam_1",
                    "tenant_id": "tenant_1",
                    "status": "published",
                    "duration_minutes": 60,
                }

            def assignment_for_student(self, _exam_id: str, _user_id: str) -> dict:
                return {"assignment_id": "assignment_1"}

            def submitted_attempt_for_student(self, *_args) -> None:
                return None

            def active_attempt_for_student(self, *_args) -> None:
                return None

            def active_attempt_for_user(self, _user_id: str) -> dict | None:
                self.active_user_checks += 1
                if self.active_user_checks == 1:
                    return None
                return {"attempt_id": "attempt_winner", "status": "in_progress"}

            def create_attempt(self, **_kwargs):
                raise RuntimeError("filtered unique index rejected race loser")

        class SessionRepository:
            def get_session(self, _session_id: str) -> None:
                return None

        repository = RaceRepository()
        service = make_service(repository)
        with patch(
            "services.exam_service.StudentRepository",
            return_value=SessionRepository(),
        ):
            with self.assertRaises(ExamServiceError) as conflict:
                service.start_attempt(
                    {
                        "exam_id": "exam_1",
                        "roll_number": "FA26-001",
                        "session_id": "session_1",
                    },
                    {
                        "user_id": "student_1",
                        "role": "student",
                        "tenant_id": "tenant_1",
                    },
                )

        self.assertEqual(conflict.exception.status_code, 409)
        self.assertEqual(conflict.exception.error, "active_attempt_conflict")
        self.assertEqual(repository.active_user_checks, 2)

    def test_concurrent_submit_loser_is_returned_as_an_idempotent_replay(self) -> None:
        attempt = {
            "attempt_id": "attempt_1",
            "tenant_id": "tenant_1",
            "exam_id": "exam_1",
            "user_id": "student_1",
            "status": "in_progress",
            "score": 0,
            "max_score": 10,
        }

        class RaceRepository:
            def get_attempt(self, _attempt_id: str) -> dict:
                return attempt

            def submit_attempt(self, _attempt_id: str) -> dict:
                return {
                    **attempt,
                    "status": "submitted",
                    "score": 8,
                    "idempotent_replay": True,
                }

            def get_attempt_responses(self, _attempt_id: str) -> list[dict]:
                return []

        result = make_service(RaceRepository()).submit_attempt(
            "attempt_1",
            False,
            {
                "user_id": "student_1",
                "role": "student",
                "tenant_id": "tenant_1",
            },
        )

        self.assertTrue(result["idempotent_replay"])
        self.assertEqual(result["status"], "submitted")
        self.assertEqual(result["score"], 8)


class ExamRouterContractTests(unittest.TestCase):
    def test_exam_and_attempt_routes_are_registered_once_by_new_routers(self) -> None:
        from infrastructure.api.fastapi_app import app

        expected = {
            ("/exams", "GET", "infrastructure.api.routers.exams"),
            ("/exams", "POST", "infrastructure.api.routers.exams"),
            ("/exams/{exam_id}", "GET", "infrastructure.api.routers.exams"),
            ("/exams/{exam_id}", "PUT", "infrastructure.api.routers.exams"),
            ("/exams/{exam_id}/publish", "POST", "infrastructure.api.routers.exams"),
            ("/exams/{exam_id}/questions", "GET", "infrastructure.api.routers.exams"),
            ("/exams/{exam_id}/questions", "POST", "infrastructure.api.routers.exams"),
            ("/exams/{exam_id}/questions/{question_id}", "PUT", "infrastructure.api.routers.exams"),
            ("/exams/{exam_id}/questions/{question_id}", "DELETE", "infrastructure.api.routers.exams"),
            ("/questions/{question_id}/options", "POST", "infrastructure.api.routers.exams"),
            ("/questions/{question_id}/options/{option_id}", "PUT", "infrastructure.api.routers.exams"),
            ("/questions/{question_id}/options/{option_id}", "DELETE", "infrastructure.api.routers.exams"),
            ("/exams/{exam_id}/assignments", "POST", "infrastructure.api.routers.exams"),
            ("/exams/{exam_id}/assignments", "GET", "infrastructure.api.routers.exams"),
            ("/exams/{exam_id}/assignments/{assignment_id}", "DELETE", "infrastructure.api.routers.exams"),
            ("/student/exams", "GET", "infrastructure.api.routers.exams"),
            ("/student/exams/join-code", "POST", "infrastructure.api.routers.exams"),
            ("/attempts/start", "POST", "infrastructure.api.routers.attempts"),
            ("/attempts/{attempt_id}", "GET", "infrastructure.api.routers.attempts"),
            ("/attempts/{attempt_id}/responses", "POST", "infrastructure.api.routers.attempts"),
            ("/attempts/{attempt_id}/submit", "POST", "infrastructure.api.routers.attempts"),
            ("/exams/{exam_id}/attendance", "GET", "infrastructure.api.routers.attempts"),
            ("/exams/{exam_id}/attempts", "GET", "infrastructure.api.routers.attempts"),
        }
        actual = set()
        relevant_paths = {item[0] for item in expected}
        for route in app.routes:
            if getattr(route, "path", "") not in relevant_paths:
                continue
            for method in route.methods or set():
                if method in {"GET", "POST", "PUT", "DELETE"}:
                    actual.add((route.path, method, route.endpoint.__module__))

        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
