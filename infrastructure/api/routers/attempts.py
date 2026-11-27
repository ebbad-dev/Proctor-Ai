from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from services.exam_service import ExamService, ExamServiceError


class AttemptStartRequest(BaseModel):
    exam_id: str
    roll_number: str
    session_id: str = ""


class AttemptResponseRequest(BaseModel):
    question_id: str
    selected_option_id: str = ""
    response_text: str = ""


class AttemptSubmitRequest(BaseModel):
    generate_report: bool = True


def create_attempt_router(
    service: ExamService,
    current_user: Callable,
    require_roles: Callable[..., Callable],
    audit: Callable[..., None],
    api_error: Callable[..., None],
) -> APIRouter:
    router = APIRouter(tags=["attempts"])

    def invoke(method: Callable, *args: Any, **kwargs: Any) -> Any:
        try:
            return method(*args, **kwargs)
        except ExamServiceError as exc:
            api_error(exc.status_code, exc.error, exc.message, exc.details)
        raise AssertionError("api_error dependency must raise")

    @router.post("/attempts/start")
    def start_attempt(
        req: AttemptStartRequest,
        request: Request,
        user: dict = Depends(require_roles("student")),
    ):
        attempt = invoke(service.start_attempt, req.model_dump(), user)
        audit(
            "attempt.started",
            actor=user,
            resource_type="attempt",
            resource_id=attempt["attempt_id"],
            request=request,
        )
        return attempt

    @router.get("/attempts/{attempt_id}")
    def get_attempt(attempt_id: str, user: dict = Depends(current_user)):
        return invoke(service.get_attempt, attempt_id, user)

    @router.post("/attempts/{attempt_id}/responses")
    def save_attempt_response(
        attempt_id: str,
        req: AttemptResponseRequest,
        request: Request,
        user: dict = Depends(require_roles("student")),
    ):
        response = invoke(service.save_response, attempt_id, req.model_dump(), user)
        audit(
            "attempt.response_saved",
            actor=user,
            resource_type="attempt",
            resource_id=attempt_id,
            details={"question_id": req.question_id},
            request=request,
        )
        return response

    @router.post("/attempts/{attempt_id}/submit")
    def submit_attempt(
        attempt_id: str,
        req: AttemptSubmitRequest,
        request: Request,
        user: dict = Depends(require_roles("student")),
    ):
        result = invoke(service.submit_attempt, attempt_id, req.generate_report, user)
        audit(
            "attempt.submit_replayed"
            if result.get("idempotent_replay")
            else "attempt.submitted",
            actor=user,
            resource_type="attempt",
            resource_id=attempt_id,
            details={
                "score": result.get("score"),
                "max_score": result.get("max_score"),
            },
            request=request,
        )
        return result

    @router.get("/exams/{exam_id}/attendance")
    def exam_attendance(
        exam_id: str,
        user: dict = Depends(require_roles("instructor", "admin")),
    ):
        return invoke(service.attendance, exam_id, user)

    @router.get("/exams/{exam_id}/attempts")
    def exam_attempts(
        exam_id: str,
        user: dict = Depends(require_roles("instructor", "admin")),
    ):
        return invoke(service.attempts_for_exam, exam_id, user)

    return router
