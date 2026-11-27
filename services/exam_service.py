from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from core.security import new_id
from core.session_lifecycle import is_active_session
from database.student_repository import StudentRepository


class ExamServiceError(Exception):
    def __init__(
        self,
        status_code: int,
        error: str,
        message: str,
        details: Any = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error = error
        self.message = message
        self.details = details


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def iso(value: Any) -> str:
    if isinstance(value, datetime):
        return parse_datetime(value).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return str(value or "")


def tenant_id(user: dict | None = None) -> str:
    return str((user or {}).get("tenant_id") or "tenant_default")


def format_exam(row: dict) -> dict:
    rules = row.get("rules_json") or row.get("rules") or {}
    if isinstance(rules, str):
        try:
            rules = json.loads(rules)
        except Exception:
            rules = {"policy": rules}
    return {
        "id": row.get("exam_id"),
        "exam_id": row.get("exam_id"),
        "tenant_id": row.get("tenant_id") or "tenant_default",
        "exam_code": row.get("exam_code") or "",
        "title": row.get("title"),
        "description": row.get("description") or "",
        "semester": row.get("semester") or "",
        "subject": row.get("subject") or "",
        "department": row.get("department") or "",
        "total_marks": int(row.get("total_marks") or 0),
        "duration_minutes": int(row.get("duration_minutes") or 60),
        "start_time": iso(row.get("start_time")) if row.get("start_time") else None,
        "end_time": iso(row.get("end_time")) if row.get("end_time") else None,
        "status": row.get("status") or "draft",
        "rules": rules,
        "assignment_id": row.get("assignment_id"),
        "assignment_status": row.get("assignment_status"),
        "assignment_count": int(row.get("assignment_count") or 0),
    }


def format_question(row: dict, *, include_correct: bool = True) -> dict:
    options = []
    for option in row.get("options") or []:
        payload = {
            "option_id": option.get("option_id"),
            "question_id": option.get("question_id"),
            "option_text": option.get("option_text") or "",
            "sort_order": int(option.get("sort_order") or 0),
        }
        if include_correct:
            payload["is_correct"] = bool(option.get("is_correct"))
        options.append(payload)
    return {
        "question_id": row.get("question_id"),
        "tenant_id": row.get("tenant_id") or "tenant_default",
        "exam_id": row.get("exam_id"),
        "question_text": row.get("question_text") or "",
        "question_type": row.get("question_type") or "mcq",
        "marks": int(row.get("marks") or 1),
        "sort_order": int(row.get("sort_order") or 0),
        "status": row.get("status") or "active",
        "options": options,
    }


def format_attempt_response(row: dict, *, include_grading: bool = False) -> dict:
    payload = {
        "response_id": row.get("response_id"),
        "attempt_id": row.get("attempt_id"),
        "question_id": row.get("question_id"),
        "selected_option_id": row.get("selected_option_id"),
        "response_text": row.get("response_text"),
        "answered_at": iso(row.get("answered_at")) if row.get("answered_at") else None,
        "updated_at": iso(row.get("updated_at")) if row.get("updated_at") else None,
    }
    if include_grading:
        payload["is_correct"] = (
            bool(row.get("is_correct")) if row.get("is_correct") is not None else None
        )
        payload["awarded_marks"] = int(row.get("awarded_marks") or 0)
    return payload


def format_attempt(
    row: dict,
    *,
    questions: list[dict] | None = None,
    responses: list[dict] | None = None,
    include_response_grading: bool = False,
) -> dict:
    return {
        "attempt_id": row.get("attempt_id"),
        "tenant_id": row.get("tenant_id") or "tenant_default",
        "exam_id": row.get("exam_id"),
        "assignment_id": row.get("assignment_id"),
        "session_id": row.get("session_id"),
        "user_id": row.get("user_id"),
        "roll_number": row.get("roll_number") or "",
        "status": row.get("status") or "in_progress",
        "started_at": iso(row.get("started_at")) if row.get("started_at") else None,
        "submitted_at": iso(row.get("submitted_at")) if row.get("submitted_at") else None,
        "score": int(row.get("score") or 0),
        "max_score": int(row.get("max_score") or 0),
        "risk_score": min(int(row.get("risk_score") or 0), 100),
        "exam": {
            "id": row.get("exam_id"),
            "exam_code": row.get("exam_code") or "",
            "title": row.get("exam_title") or "",
            "duration_minutes": int(row.get("duration_minutes") or 60),
            "total_marks": int(row.get("total_marks") or row.get("max_score") or 0),
        },
        "student": {
            "id": row.get("user_id"),
            "name": row.get("student_name") or "",
            "email": row.get("student_email") or "",
        },
        "questions": questions or [],
        "responses": [
            format_attempt_response(response, include_grading=include_response_grading)
            for response in (responses or [])
        ],
    }


def format_assignment(row: dict) -> dict:
    return {
        "assignment_id": row.get("assignment_id"),
        "tenant_id": row.get("tenant_id") or "tenant_default",
        "exam_id": row.get("exam_id"),
        "student_user_id": row.get("student_user_id"),
        "student_email": row.get("student_email") or "",
        "student_name": row.get("student_name") or "",
        "student_active": bool(row.get("student_active", True)),
        "assigned_at": iso(row.get("assigned_at")) if row.get("assigned_at") else None,
        "status": row.get("status") or "assigned",
    }


def _ignore_failure(_event: str, **_fields: Any) -> None:
    return None


@dataclass
class ExamService:
    repository_provider: Callable[[], Any]
    database_provider: Callable[[], Any]
    get_active_session_id: Callable[[], str]
    clear_active_session: Callable[[str], None]
    write_active_proctor_state: Callable[..., None]
    session_meta: dict
    session_store: dict[str, dict]
    get_session_events: Callable[[str], list[dict]]
    generate_report_file: Callable[[str], str]
    report_metadata: Callable[[str, str], dict]
    reports_dir: str
    log_failure: Callable[..., None] = _ignore_failure
    now: Callable[[], datetime] = utc_now
    session_id_factory: Callable[[], str] = field(
        default_factory=lambda: lambda: new_id("session")
    )

    def validate_exam_payload(self, data: dict) -> dict:
        payload = dict(data)
        payload["exam_code"] = "".join(
            ch
            for ch in (payload.get("exam_code") or "").upper().strip()
            if ch.isalnum() or ch in "-_"
        )
        for key in ("title", "description", "semester", "subject", "department"):
            payload[key] = (payload.get(key) or "").strip()
        if not payload["title"]:
            self._fail(422, "validation_error", "Exam title is required.")
        if int(payload.get("total_marks") or 0) < 0:
            self._fail(422, "validation_error", "Total marks cannot be negative.")
        payload["status"] = self.validate_exam_status(payload.get("status") or "draft")
        rules = payload.get("rules")
        if rules is None:
            payload["rules"] = {}
        elif isinstance(rules, str):
            payload["rules"] = {"policy": rules.strip()} if rules.strip() else {}
        elif not isinstance(rules, dict):
            self._fail(422, "validation_error", "Exam rules must be text or a JSON object.")
        if int(payload.get("duration_minutes") or 0) < 1:
            self._fail(422, "validation_error", "Exam duration must be at least one minute.")
        if payload.get("start_time") and payload.get("end_time"):
            try:
                if parse_datetime(payload["end_time"]) <= parse_datetime(payload["start_time"]):
                    self._fail(
                        422,
                        "validation_error",
                        "Exam end time must be after start time.",
                    )
            except ExamServiceError:
                raise
            except Exception as exc:
                raise ExamServiceError(
                    422,
                    "validation_error",
                    "Exam start/end times must be valid ISO date strings.",
                ) from exc
        return payload

    def validate_exam_status(self, status: str) -> str:
        normalized = (status or "draft").strip().lower()
        if normalized not in {"draft", "published", "scheduled", "archived", "closed"}:
            self._fail(
                422,
                "validation_error",
                "Exam status must be draft, scheduled, published, closed, or archived.",
            )
        return normalized

    def validate_question_payload(self, data: dict) -> dict:
        payload = dict(data)
        payload["question_text"] = (payload.get("question_text") or "").strip()
        payload["question_type"] = (payload.get("question_type") or "mcq").strip().lower()
        if payload["question_type"] != "mcq":
            self._fail(422, "validation_error", "Only MCQ questions are supported in this version.")
        if len(payload["question_text"]) < 3:
            self._fail(422, "validation_error", "Question text is required.")
        if int(payload.get("marks") or 0) < 1:
            self._fail(422, "validation_error", "Question marks must be at least 1.")
        clean_options = []
        for index, option in enumerate(payload.get("options") or []):
            text = str(option.get("option_text") or "").strip()
            if not text:
                continue
            clean_options.append(
                {
                    "option_id": option.get("option_id") or "",
                    "option_text": text,
                    "is_correct": bool(option.get("is_correct")),
                    "sort_order": int(
                        option.get("sort_order")
                        if option.get("sort_order") is not None
                        else index
                    ),
                }
            )
        if len(clean_options) < 2:
            self._fail(422, "validation_error", "Add at least two answer options.")
        if not any(option["is_correct"] for option in clean_options):
            self._fail(422, "validation_error", "Mark one option as correct.")
        payload["options"] = clean_options
        return payload

    def list_exams(self, user: dict) -> list[dict]:
        return [format_exam(row) for row in self.repository_provider().list_exams(user)]

    def create_exam(self, data: dict, user: dict) -> dict:
        payload = self.validate_exam_payload(data)
        if payload["status"] in {"published", "scheduled"}:
            self._fail(
                422,
                "validation_error",
                "Create the exam as a draft, add questions, then publish or schedule it.",
            )
        exam = self.repository_provider().create_exam(
            payload,
            user["user_id"],
            tenant_id(user),
        )
        return format_exam(exam)

    def get_exam(self, exam_id: str, user: dict) -> dict:
        repo = self.repository_provider()
        row = repo.get_exam(exam_id)
        if not row:
            self._fail(404, "not_found", "Exam not found.")
        if user["role"] == "student" and not repo.exam_assigned_to_student(
            exam_id, user["user_id"]
        ):
            self._fail(403, "forbidden", "This exam is not assigned to you.")
        if user["role"] == "instructor" and (
            row.get("tenant_id") or "tenant_default"
        ) != tenant_id(user):
            self._fail(403, "forbidden", "This exam belongs to another institution.")
        return format_exam(row)

    def update_exam(self, exam_id: str, data: dict, user: dict) -> dict:
        self.require_management_access(exam_id, user)
        repo = self.repository_provider()
        payload = self.validate_exam_payload(data)
        if payload["status"] in {"published", "scheduled"}:
            question_marks = self.validate_exam_content(
                exam_id, int(payload.get("total_marks") or 0)
            )
            if int(payload.get("total_marks") or 0) == 0:
                payload["total_marks"] = question_marks
        row = repo.update_exam(exam_id, payload)
        if not row:
            self._fail(404, "not_found", "Exam not found.")
        return format_exam(row)

    def publish_exam(self, exam_id: str, user: dict) -> dict:
        repo = self.repository_provider()
        exam = self.require_management_access(exam_id, user)
        declared_marks = int(exam.get("total_marks") or 0)
        question_marks = self.validate_exam_content(exam_id, declared_marks)
        if declared_marks == 0:
            repo.update_exam(exam_id, {"total_marks": question_marks})
        return format_exam(repo.publish_exam(exam_id))

    def list_questions(self, exam_id: str, user: dict) -> list[dict]:
        repo = self.repository_provider()
        row = repo.get_exam(exam_id)
        if not row:
            self._fail(404, "not_found", "Exam not found.")
        include_correct = user["role"] in {"instructor", "admin"}
        if user["role"] == "student" and not repo.exam_assigned_to_student(
            exam_id, user["user_id"]
        ):
            self._fail(403, "forbidden", "This exam is not assigned to you.")
        if user["role"] == "instructor" and (
            row.get("tenant_id") or "tenant_default"
        ) != tenant_id(user):
            self._fail(403, "forbidden", "This exam belongs to another institution.")
        return [
            format_question(question, include_correct=include_correct)
            for question in repo.list_exam_questions(
                exam_id, include_correct=include_correct
            )
        ]

    def create_question(self, exam_id: str, data: dict, user: dict) -> dict:
        repo = self.repository_provider()
        exam = self.require_management_access(exam_id, user)
        self.require_content_editable(exam)
        question = repo.upsert_question(
            exam_id,
            self.validate_question_payload(data),
            exam.get("tenant_id") or tenant_id(user),
        )
        rows = [
            row
            for row in repo.list_exam_questions(exam_id, include_correct=True)
            if row.get("question_id") == question.get("question_id")
        ]
        return format_question(rows[0]) if rows else format_question(question)

    def update_question(
        self,
        exam_id: str,
        question_id: str,
        data: dict,
        user: dict,
    ) -> dict:
        repo = self.repository_provider()
        exam = self.require_management_access(exam_id, user)
        self.require_content_editable(exam)
        existing = repo.get_question(question_id)
        if not existing or existing.get("exam_id") != exam_id:
            self._fail(404, "not_found", "Question not found.")
        repo.upsert_question(
            exam_id,
            self.validate_question_payload(data),
            exam.get("tenant_id") or tenant_id(user),
            question_id,
        )
        rows = [
            row
            for row in repo.list_exam_questions(exam_id, include_correct=True)
            if row.get("question_id") == question_id
        ]
        return format_question(rows[0]) if rows else {}

    def delete_question(self, exam_id: str, question_id: str, user: dict) -> dict:
        repo = self.repository_provider()
        exam = self.require_management_access(exam_id, user)
        self.require_content_editable(exam)
        existing = repo.get_question(question_id)
        if not existing or existing.get("exam_id") != exam_id:
            self._fail(404, "not_found", "Question not found.")
        repo.delete_question(question_id)
        return {"status": "ok", "question_id": question_id}

    def save_option(
        self,
        question_id: str,
        data: dict,
        user: dict,
        option_id: str = "",
    ) -> dict:
        repo = self.repository_provider()
        question = repo.get_question(question_id)
        if not question:
            self._fail(404, "not_found", "Question not found.")
        exam = self.require_management_access(question["exam_id"], user)
        self.require_content_editable(exam)
        text = (data.get("option_text") or "").strip()
        if not text:
            self._fail(422, "validation_error", "Option text is required.")
        return repo.upsert_option(
            question_id,
            {**data, "option_text": text},
            question.get("tenant_id") or tenant_id(user),
            option_id,
        )

    def delete_option(self, question_id: str, option_id: str, user: dict) -> dict:
        repo = self.repository_provider()
        question = repo.get_question(question_id)
        if not question:
            self._fail(404, "not_found", "Question not found.")
        exam = self.require_management_access(question["exam_id"], user)
        self.require_content_editable(exam)
        option = repo.get_option(option_id)
        if not option or option.get("question_id") != question_id:
            self._fail(404, "not_found", "Option not found.")
        repo.delete_option(option_id)
        return {"status": "ok", "option_id": option_id}

    def assign_exam(self, exam_id: str, student_email: str, user: dict) -> dict:
        repo = self.repository_provider()
        exam = self.require_management_access(exam_id, user)
        student = repo.get_user_by_email((student_email or "").strip().lower())
        if not student or student.get("role") != "student":
            self._fail(
                404,
                "student_not_found",
                "A student account with that email was not found.",
            )
        if (student.get("tenant_id") or "tenant_default") != (
            exam.get("tenant_id") or tenant_id(user)
        ):
            self._fail(
                403,
                "forbidden",
                "Student must belong to the same institution as the exam.",
            )
        return repo.assign_exam(
            exam_id,
            student["user_id"],
            user["user_id"],
            exam.get("tenant_id") or tenant_id(user),
        )

    def list_assignments(self, exam_id: str, user: dict) -> list[dict]:
        self.require_management_access(exam_id, user)
        return [
            format_assignment(row)
            for row in self.repository_provider().list_exam_assignments(exam_id)
        ]

    def revoke_assignment(
        self, exam_id: str, assignment_id: str, user: dict
    ) -> dict:
        self.require_management_access(exam_id, user)
        row = self.repository_provider().revoke_assignment(assignment_id)
        if not row or row.get("exam_id") != exam_id:
            self._fail(404, "not_found", "Assignment not found.")
        return row

    def join_by_code(self, exam_code: str, user: dict) -> dict:
        repo = self.repository_provider()
        code = (exam_code or "").strip()
        if not code:
            self._fail(422, "validation_error", "Enter an exam code.")
        exam = repo.get_exam_by_code(code, tenant_id(user))
        if not exam:
            self._fail(404, "not_found", "No published exam was found for that code.")
        if (exam.get("status") or "").lower() not in {"published", "scheduled"}:
            self._fail(
                403,
                "exam_unavailable",
                "This exam code is not open for students.",
            )
        assignment = repo.ensure_code_assignment(
            exam["exam_id"],
            user["user_id"],
            exam.get("tenant_id") or tenant_id(user),
        )
        formatted = format_exam(
            {
                **exam,
                "assignment_id": assignment.get("assignment_id"),
                "assignment_status": assignment.get("status") or "assigned",
            }
        )
        return {**formatted, "assignment_id": assignment.get("assignment_id")}

    def start_attempt(self, data: dict, user: dict) -> dict:
        repo = self.repository_provider()
        exam_id = str(data.get("exam_id") or "")
        exam = repo.get_exam(exam_id)
        if not exam:
            self._fail(404, "not_found", "Exam not found.")
        if (exam.get("status") or "").lower() not in {"published", "scheduled"}:
            self._fail(403, "exam_unavailable", "This exam is not open for attempts.")
        self.require_exam_window(exam)
        assignment = repo.assignment_for_student(exam_id, user["user_id"])
        if not assignment:
            self._fail(
                403,
                "forbidden",
                "This exam is not assigned to you. Join by exam code first if your instructor provided one.",
            )
        roll_number = (data.get("roll_number") or "").strip()
        if len(roll_number) < 2:
            self._fail(
                422,
                "validation_error",
                "Official university roll number is required.",
            )
        if repo.submitted_attempt_for_student(exam_id, user["user_id"]):
            self._fail(
                409,
                "attempt_locked",
                "This exam has already been submitted. Reattempt is locked.",
            )

        active = repo.active_attempt_for_student(exam_id, user["user_id"])
        if active and self.attempt_expired(
            {**active, "duration_minutes": exam.get("duration_minutes")}
        ):
            repo.submit_attempt(active["attempt_id"])
            self._stop_active_proctor(active.get("session_id") or "")
            self._fail(
                409,
                "attempt_locked",
                "The previous attempt reached its time limit and was submitted automatically.",
            )
        if active:
            attempt = active
        else:
            competing = repo.active_attempt_for_user(user["user_id"])
            if competing:
                if self.attempt_expired(competing):
                    repo.submit_attempt(competing["attempt_id"])
                    self._stop_active_proctor(competing.get("session_id") or "")
                    self._fail(
                        409,
                        "attempt_locked",
                        "A previous active attempt reached its time limit and was submitted automatically. Retry starting this exam.",
                    )
                self._fail(
                    409,
                    "active_attempt_conflict",
                    "Finish the active exam attempt before starting another exam.",
                )

            session_id = str(data.get("session_id") or self.session_id_factory())
            db = self.database_provider()
            if not db or not getattr(db, "is_active", False):
                self._fail(
                    503,
                    "database_unavailable",
                    "Attempt persistence is unavailable. Retry attempt start.",
                )
            session_repo = StudentRepository(db)
            existing_session = session_repo.get_session(session_id)
            if existing_session:
                if existing_session.get("user_id") != user["user_id"]:
                    self._fail(
                        403,
                        "forbidden",
                        "The requested session belongs to another student.",
                    )
                if not is_active_session(existing_session.get("status")):
                    self._fail(
                        409,
                        "session_closed",
                        "A completed session cannot be reused for a new attempt.",
                    )
                if existing_session.get("exam_id") and existing_session.get(
                    "exam_id"
                ) != exam_id:
                    self._fail(
                        409,
                        "session_exam_conflict",
                        "The requested session belongs to another exam.",
                    )
            active_proctor_session = self.get_active_session_id()
            if active_proctor_session and active_proctor_session != session_id:
                self._fail(
                    409,
                    "proctor_busy",
                    "Stop the active proctor session before starting another attempt.",
                )
            try:
                attempt = repo.create_attempt(
                    exam_id=exam_id,
                    user_id=user["user_id"],
                    roll_number=roll_number,
                    assignment_id=assignment.get("assignment_id") or "",
                    session_id=session_id,
                    tenant_id=exam.get("tenant_id") or tenant_id(user),
                )
            except Exception as exc:
                if repo.active_attempt_for_user(user["user_id"]):
                    self._fail(
                        409,
                        "active_attempt_conflict",
                        "An active exam attempt already exists.",
                    )
                self.log_failure(
                    "attempt.start_failed",
                    exam_id=exam_id,
                    user_id=user["user_id"],
                    error=exc.__class__.__name__,
                )
                raise ExamServiceError(
                    503,
                    "attempt_not_started",
                    "The attempt could not be persisted. Retry attempt start.",
                ) from exc
            try:
                session_repo.upsert_session(
                    session_id,
                    student_id=user["user_id"],
                    student_name=user.get("full_name", ""),
                    exam_code=exam.get("exam_code") or exam.get("title") or exam_id,
                    user_id=user["user_id"],
                    exam_id=exam_id,
                    roll_number=roll_number,
                    tenant_id=exam.get("tenant_id") or tenant_id(user),
                    start_time=self.now(),
                    status="Active",
                )
                persisted_session_status = session_repo.get_session_status(session_id)
            except Exception as exc:
                try:
                    repo.cancel_attempt_start(attempt["attempt_id"])
                except Exception:
                    pass
                self.log_failure(
                    "attempt.session_start_failed",
                    attempt_id=attempt.get("attempt_id"),
                    session_id=session_id,
                    error=exc.__class__.__name__,
                )
                raise ExamServiceError(
                    503,
                    "session_not_persisted",
                    "The attempt session could not be persisted. Retry attempt start.",
                ) from exc
            if not is_active_session(persisted_session_status):
                try:
                    repo.cancel_attempt_start(attempt["attempt_id"])
                except Exception:
                    pass
                self._fail(
                    409,
                    "session_closed",
                    "The session ended while the attempt was starting. Start with a new session.",
                )
            now = self.now().isoformat()
            self.session_meta.update(
                {
                    "session_id": session_id,
                    "student_id": user["user_id"],
                    "exam_code": exam.get("exam_code") or exam_id,
                    "user_id": user["user_id"],
                    "started_at": now,
                }
            )
            self.session_store[session_id] = {
                "session_id": session_id,
                "user_id": user["user_id"],
                "student_id": user["user_id"],
                "student_name": user.get("full_name", ""),
                "roll_number": roll_number,
                "exam_id": exam_id,
                "exam_code": exam.get("exam_code") or "",
                "tenant_id": exam.get("tenant_id") or tenant_id(user),
                "status": "Active",
                "started_at": now,
            }
            self.write_active_proctor_state(
                True,
                session_id,
                user["user_id"],
                exam.get("exam_code") or exam_id,
            )
        questions = [
            format_question(question, include_correct=False)
            for question in repo.list_exam_questions(exam_id, include_correct=False)
        ]
        return format_attempt(
            attempt,
            questions=questions,
            responses=repo.get_attempt_responses(attempt["attempt_id"]),
        )

    def get_attempt(self, attempt_id: str, user: dict) -> dict:
        repo = self.repository_provider()
        attempt = repo.get_attempt(attempt_id)
        if not attempt:
            self._fail(404, "not_found", "Attempt not found.")
        if user["role"] == "student" and attempt.get("user_id") != user["user_id"]:
            self._fail(403, "forbidden", "You can only access your own attempts.")
        if user["role"] == "instructor" and (
            attempt.get("tenant_id") or "tenant_default"
        ) != tenant_id(user):
            self._fail(
                403,
                "forbidden",
                "This attempt belongs to another institution.",
            )
        if attempt.get("status") == "in_progress" and self.attempt_expired(attempt):
            attempt = repo.submit_attempt(attempt_id) or attempt
            self._stop_active_proctor(attempt.get("session_id") or "")
        include_correct = user["role"] in {"instructor", "admin"}
        questions = [
            format_question(question, include_correct=include_correct)
            for question in repo.list_exam_questions(
                attempt["exam_id"], include_correct=include_correct
            )
        ]
        return format_attempt(
            attempt,
            questions=questions,
            responses=repo.get_attempt_responses(attempt_id),
            include_response_grading=include_correct,
        )

    def save_response(
        self, attempt_id: str, data: dict, user: dict
    ) -> dict:
        repo = self.repository_provider()
        attempt = repo.get_attempt(attempt_id)
        if not attempt:
            self._fail(404, "not_found", "Attempt not found.")
        if attempt.get("user_id") != user["user_id"]:
            self._fail(403, "forbidden", "You can only update your own attempt.")
        if attempt.get("status") != "in_progress":
            self._fail(409, "attempt_locked", "This attempt is no longer active.")
        if self.attempt_expired(attempt):
            repo.submit_attempt(attempt_id)
            self._stop_active_proctor(attempt.get("session_id") or "")
            self._fail(
                409,
                "attempt_expired",
                "The exam time limit was reached and the attempt was submitted automatically.",
            )
        question_id = str(data.get("question_id") or "")
        question = repo.get_question(question_id)
        if not question or question.get("exam_id") != attempt.get("exam_id"):
            self._fail(404, "not_found", "Question not found for this attempt.")
        selected_option_id = str(data.get("selected_option_id") or "")
        if selected_option_id:
            option = repo.get_option(selected_option_id)
            if not option or option.get("question_id") != question_id:
                self._fail(
                    422,
                    "validation_error",
                    "Selected option does not belong to this question.",
                )
        response = repo.save_response(
            attempt_id=attempt_id,
            question_id=question_id,
            selected_option_id=selected_option_id,
            response_text=str(data.get("response_text") or ""),
            tenant_id=attempt.get("tenant_id") or tenant_id(user),
        )
        return format_attempt_response(response, include_grading=False)

    def submit_attempt(
        self, attempt_id: str, generate_report: bool, user: dict
    ) -> dict:
        repo = self.repository_provider()
        attempt = repo.get_attempt(attempt_id)
        if not attempt:
            self._fail(404, "not_found", "Attempt not found.")
        if attempt.get("user_id") != user["user_id"]:
            self._fail(403, "forbidden", "You can only submit your own attempt.")
        if attempt.get("status") not in {"in_progress", "submitted"}:
            self._fail(
                409,
                "invalid_attempt_state",
                "This attempt cannot be submitted from its current state.",
            )
        idempotent_replay = attempt.get("status") == "submitted"
        try:
            submitted = repo.submit_attempt(attempt_id)
        except ValueError as exc:
            raise ExamServiceError(
                409,
                "invalid_attempt_state",
                "This attempt cannot be submitted from its current state.",
            ) from exc
        if not submitted:
            self._fail(500, "submit_failed", "Could not submit attempt.")
        idempotent_replay = bool(
            submitted.get("idempotent_replay", idempotent_replay)
        )
        if submitted.get("session_id"):
            submitted = dict(submitted)
            submitted["risk_score"] = min(
                sum(
                    int(row.get("risk_points") or 0)
                    for row in self.get_session_events(submitted["session_id"])
                ),
                100,
            )
        self._stop_active_proctor(submitted.get("session_id") or "")
        report = None
        if generate_report and submitted.get("session_id"):
            try:
                existing_path = os.path.join(
                    self.reports_dir,
                    f"{submitted['session_id']}_report.pdf",
                )
                path = (
                    existing_path
                    if idempotent_replay and os.path.exists(existing_path)
                    else self.generate_report_file(submitted["session_id"])
                )
                report = self.report_metadata(submitted["session_id"], path)
            except Exception:
                report = None
        return {
            **format_attempt(
                submitted,
                responses=repo.get_attempt_responses(attempt_id),
            ),
            "report": report,
            "idempotent_replay": idempotent_replay,
        }

    def attendance(self, exam_id: str, user: dict) -> list[dict]:
        self.require_management_access(exam_id, user)
        return [
            {
                **row,
                "started_at": iso(row.get("started_at")) if row.get("started_at") else None,
                "submitted_at": (
                    iso(row.get("submitted_at")) if row.get("submitted_at") else None
                ),
                "attempt_status": row.get("attempt_status") or "not_started",
                "risk_score": min(int(row.get("risk_score") or 0), 100),
            }
            for row in self.repository_provider().exam_attendance(exam_id)
        ]

    def attempts_for_exam(self, exam_id: str, user: dict) -> list[dict]:
        self.require_management_access(exam_id, user)
        repo = self.repository_provider()
        questions = [
            format_question(question, include_correct=True)
            for question in repo.list_exam_questions(exam_id, include_correct=True)
        ]
        return [
            format_attempt(
                row,
                questions=questions,
                responses=repo.get_attempt_responses(row["attempt_id"]),
                include_response_grading=True,
            )
            for row in repo.list_attempts_for_exam(exam_id)
        ]

    def validate_exam_content(self, exam_id: str, declared_marks: int = 0) -> int:
        questions = self.repository_provider().list_exam_questions(
            exam_id, include_correct=True
        )
        if not questions:
            self._fail(
                422,
                "validation_error",
                "Add at least one valid question before publishing or scheduling.",
            )
        question_marks = sum(int(question.get("marks") or 0) for question in questions)
        if declared_marks not in {0, question_marks}:
            self._fail(
                422,
                "marks_mismatch",
                f"Declared total marks ({declared_marks}) must match the question total ({question_marks}).",
            )
        return question_marks

    def require_content_editable(self, exam: dict) -> None:
        if (exam.get("status") or "draft").lower() in {"published", "scheduled"}:
            self._fail(
                409,
                "exam_content_locked",
                "Return the exam to draft status before changing published questions or options.",
            )

    def require_management_access(self, exam_id: str, user: dict) -> dict:
        row = self.repository_provider().get_exam(exam_id)
        if not row:
            self._fail(404, "not_found", "Exam not found.")
        if user.get("role") != "admin" and (
            row.get("tenant_id") or "tenant_default"
        ) != tenant_id(user):
            self._fail(403, "forbidden", "This exam belongs to another institution.")
        return row

    def require_exam_window(self, exam: dict) -> None:
        try:
            now = self.now()
            if exam.get("start_time") and now < parse_datetime(exam["start_time"]):
                self._fail(403, "exam_not_started", "This exam is not open yet.")
            if exam.get("end_time") and now >= parse_datetime(exam["end_time"]):
                self._fail(403, "exam_closed", "This exam window has closed.")
        except ExamServiceError:
            raise
        except Exception as exc:
            raise ExamServiceError(
                500,
                "invalid_exam_schedule",
                "The exam schedule is invalid. Ask the instructor to correct it.",
            ) from exc

    def attempt_expired(self, attempt: dict) -> bool:
        if not attempt.get("started_at"):
            return False
        try:
            duration = max(1, int(attempt.get("duration_minutes") or 60))
            return self.now() >= parse_datetime(attempt["started_at"]) + timedelta(
                minutes=duration
            )
        except Exception:
            return False

    def _stop_active_proctor(self, session_id: str) -> None:
        if session_id and self.get_active_session_id() == session_id:
            self.write_active_proctor_state(False)
            self.clear_active_session(session_id)

    @staticmethod
    def _fail(
        status_code: int,
        error: str,
        message: str,
        details: Any = None,
    ) -> None:
        raise ExamServiceError(status_code, error, message, details)
