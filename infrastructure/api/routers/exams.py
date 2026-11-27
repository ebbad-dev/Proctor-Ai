from __future__ import annotations

from typing import Any, Callable, List, Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from services.exam_service import ExamService, ExamServiceError


class ExamRequest(BaseModel):
    exam_code: str = ""
    title: str
    description: str = ""
    semester: str = ""
    subject: str = ""
    department: str = ""
    total_marks: int = 0
    duration_minutes: int = 60
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    status: str = "draft"
    rules: Any = None


class QuestionOptionRequest(BaseModel):
    option_id: str = ""
    option_text: str = ""
    is_correct: bool = False
    sort_order: int = 0


class ExamQuestionRequest(BaseModel):
    question_id: str = ""
    question_text: str
    question_type: str = "mcq"
    marks: int = 1
    sort_order: int = 0
    status: str = "active"
    options: List[QuestionOptionRequest] = Field(default_factory=list)


class ExamCodeJoinRequest(BaseModel):
    exam_code: str


class AssignmentRequest(BaseModel):
    student_email: str


class AssignmentItem(BaseModel):
    assignment_id: str
    tenant_id: Optional[str] = None
    exam_id: str
    student_user_id: str
    student_email: str = ""
    student_name: str = ""
    student_active: bool = True
    assigned_at: Optional[Any] = None
    status: str = "assigned"


def create_exam_router(
    service: ExamService,
    current_user: Callable,
    require_roles: Callable[..., Callable],
    audit: Callable[..., None],
    api_error: Callable[..., None],
) -> APIRouter:
    router = APIRouter(tags=["exams"])

    def invoke(method: Callable, *args: Any, **kwargs: Any) -> Any:
        try:
            return method(*args, **kwargs)
        except ExamServiceError as exc:
            api_error(exc.status_code, exc.error, exc.message, exc.details)
        raise AssertionError("api_error dependency must raise")

    @router.get("/exams")
    def list_exams(user: dict = Depends(require_roles("instructor", "admin"))):
        return invoke(service.list_exams, user)

    @router.post("/exams")
    def create_exam(
        req: ExamRequest,
        request: Request,
        user: dict = Depends(require_roles("instructor", "admin")),
    ):
        exam = invoke(service.create_exam, req.model_dump(), user)
        audit(
            "exam.created",
            actor=user,
            resource_type="exam",
            resource_id=exam.get("exam_id", ""),
            request=request,
        )
        return exam

    @router.get("/exams/{exam_id}")
    def get_exam(exam_id: str, user: dict = Depends(current_user)):
        return invoke(service.get_exam, exam_id, user)

    @router.put("/exams/{exam_id}")
    def update_exam(
        exam_id: str,
        req: ExamRequest,
        request: Request,
        user: dict = Depends(require_roles("instructor", "admin")),
    ):
        exam = invoke(service.update_exam, exam_id, req.model_dump(), user)
        audit(
            "exam.updated",
            actor=user,
            resource_type="exam",
            resource_id=exam_id,
            request=request,
        )
        return exam

    @router.post("/exams/{exam_id}/publish")
    def publish_exam(
        exam_id: str,
        request: Request,
        user: dict = Depends(require_roles("instructor", "admin")),
    ):
        exam = invoke(service.publish_exam, exam_id, user)
        audit(
            "exam.published",
            actor=user,
            resource_type="exam",
            resource_id=exam_id,
            request=request,
        )
        return exam

    @router.get("/exams/{exam_id}/questions")
    def list_exam_questions(exam_id: str, user: dict = Depends(current_user)):
        return invoke(service.list_questions, exam_id, user)

    @router.post("/exams/{exam_id}/questions")
    def create_exam_question(
        exam_id: str,
        req: ExamQuestionRequest,
        request: Request,
        user: dict = Depends(require_roles("instructor", "admin")),
    ):
        question = invoke(service.create_question, exam_id, req.model_dump(), user)
        audit(
            "exam.question_saved",
            actor=user,
            resource_type="exam",
            resource_id=exam_id,
            request=request,
        )
        return question

    @router.put("/exams/{exam_id}/questions/{question_id}")
    def update_exam_question(
        exam_id: str,
        question_id: str,
        req: ExamQuestionRequest,
        request: Request,
        user: dict = Depends(require_roles("instructor", "admin")),
    ):
        question = invoke(
            service.update_question,
            exam_id,
            question_id,
            req.model_dump(),
            user,
        )
        audit(
            "exam.question_saved",
            actor=user,
            resource_type="question",
            resource_id=question_id,
            request=request,
        )
        return question

    @router.delete("/exams/{exam_id}/questions/{question_id}")
    def delete_exam_question(
        exam_id: str,
        question_id: str,
        request: Request,
        user: dict = Depends(require_roles("instructor", "admin")),
    ):
        result = invoke(service.delete_question, exam_id, question_id, user)
        audit(
            "exam.question_deleted",
            actor=user,
            resource_type="question",
            resource_id=question_id,
            request=request,
        )
        return result

    @router.post("/questions/{question_id}/options")
    def create_question_option(
        question_id: str,
        req: QuestionOptionRequest,
        request: Request,
        user: dict = Depends(require_roles("instructor", "admin")),
    ):
        option = invoke(service.save_option, question_id, req.model_dump(), user)
        audit(
            "question.option_saved",
            actor=user,
            resource_type="question",
            resource_id=question_id,
            request=request,
        )
        return option

    @router.put("/questions/{question_id}/options/{option_id}")
    def update_question_option(
        question_id: str,
        option_id: str,
        req: QuestionOptionRequest,
        request: Request,
        user: dict = Depends(require_roles("instructor", "admin")),
    ):
        option = invoke(
            service.save_option,
            question_id,
            req.model_dump(),
            user,
            option_id,
        )
        audit(
            "question.option_saved",
            actor=user,
            resource_type="option",
            resource_id=option_id,
            request=request,
        )
        return option

    @router.delete("/questions/{question_id}/options/{option_id}")
    def delete_question_option(
        question_id: str,
        option_id: str,
        request: Request,
        user: dict = Depends(require_roles("instructor", "admin")),
    ):
        result = invoke(service.delete_option, question_id, option_id, user)
        audit(
            "question.option_deleted",
            actor=user,
            resource_type="option",
            resource_id=option_id,
            request=request,
        )
        return result

    @router.post("/exams/{exam_id}/assignments")
    def assign_exam(
        exam_id: str,
        req: AssignmentRequest,
        request: Request,
        user: dict = Depends(require_roles("instructor", "admin")),
    ):
        assignment = invoke(service.assign_exam, exam_id, req.student_email, user)
        audit(
            "exam.assigned",
            actor=user,
            resource_type="exam",
            resource_id=exam_id,
            details={"student_user_id": assignment.get("student_user_id")},
            request=request,
        )
        return assignment

    @router.get("/exams/{exam_id}/assignments", response_model=List[AssignmentItem])
    def list_exam_assignments(
        exam_id: str,
        user: dict = Depends(require_roles("instructor", "admin")),
    ):
        return invoke(service.list_assignments, exam_id, user)

    @router.delete("/exams/{exam_id}/assignments/{assignment_id}")
    def revoke_exam_assignment(
        exam_id: str,
        assignment_id: str,
        request: Request,
        user: dict = Depends(require_roles("instructor", "admin")),
    ):
        row = invoke(service.revoke_assignment, exam_id, assignment_id, user)
        audit(
            "exam.assignment_revoked",
            actor=user,
            resource_type="exam",
            resource_id=exam_id,
            details={
                "assignment_id": assignment_id,
                "student_user_id": row.get("student_user_id"),
            },
            request=request,
        )
        return {"status": "ok", "assignment_id": assignment_id}

    @router.get("/student/exams")
    def student_exams(user: dict = Depends(require_roles("student"))):
        return invoke(service.list_exams, user)

    @router.post("/student/exams/join-code")
    def join_exam_by_code(
        req: ExamCodeJoinRequest,
        request: Request,
        user: dict = Depends(require_roles("student")),
    ):
        exam = invoke(service.join_by_code, req.exam_code, user)
        audit(
            "exam.code_joined",
            actor=user,
            resource_type="exam",
            resource_id=exam["exam_id"],
            details={
                "exam_code": req.exam_code,
                "assignment_id": exam.get("assignment_id"),
            },
            request=request,
        )
        return exam

    return router
