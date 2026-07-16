from __future__ import annotations

import secrets
from datetime import UTC, datetime

from core.security import hash_password, new_id
from database.db_connection import DatabaseConnection
from database.platform_repository import PlatformRepository
from database.student_repository import StudentRepository


def main() -> None:
    db = DatabaseConnection()
    if not db.connect(max_retries=1):
        raise SystemExit("SQL Server connection failed")

    repo = PlatformRepository(db)
    student_repo = StudentRepository(db)
    tenant = repo.ensure_default_tenant()

    suffix = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    instructor_password_hash = hash_password(secrets.token_urlsafe(32))
    student_password_hash = hash_password(secrets.token_urlsafe(32))
    instructor = repo.create_user(
        f"smoke.instructor.{suffix}@proctorai.local",
        "Smoke Instructor",
        "instructor",
        instructor_password_hash,
        tenant["tenant_id"],
    )
    student = repo.create_user(
        f"smoke.student.{suffix}@proctorai.local",
        "Smoke Student",
        "student",
        student_password_hash,
        tenant["tenant_id"],
    )
    exam = repo.create_exam(
        {
            "title": f"SQL Smoke Exam {suffix}",
            "description": "Automated live SQL Server smoke exam.",
            "duration_minutes": 15,
            "status": "published",
            "rules": {"browser_guard_required": False},
        },
        instructor["user_id"],
        tenant["tenant_id"],
    )
    assignment = repo.assign_exam(exam["exam_id"], student["user_id"], instructor["user_id"], tenant["tenant_id"])

    session_id = new_id("smoke_session")
    student_repo.upsert_session(
        session_id,
        student_id=student["user_id"],
        student_name=student["full_name"],
        exam_code=exam["exam_id"],
        user_id=student["user_id"],
        exam_id=exam["exam_id"],
        tenant_id=tenant["tenant_id"],
        status="Active",
    )
    student_repo.insert_event(
        session_id,
        student["user_id"],
        "Tab Switch",
        datetime.now(UTC),
        12,
        "Smoke event persisted through SQL Server.",
        tenant["tenant_id"],
    )
    repo.end_session(session_id)
    repo.write_audit_log(
        "smoke.sql_server.completed",
        actor=instructor,
        resource_type="session",
        resource_id=session_id,
        details={"exam_id": exam["exam_id"], "assignment_id": assignment["assignment_id"]},
    )

    session = student_repo.get_session(session_id)
    events = student_repo.get_events(session_id)
    audits = repo.list_audit_logs(tenant["tenant_id"], 5)

    print(
        {
            "connected": True,
            "tenant": tenant["tenant_id"],
            "student_user_id": student["user_id"],
            "instructor_user_id": instructor["user_id"],
            "exam_id": exam["exam_id"],
            "assignment_id": assignment["assignment_id"],
            "session_id": session_id,
            "session_status": session.get("status") if session else None,
            "event_count": len(events),
            "risk_score": session.get("final_score") if session else None,
            "latest_audit_action": audits[0].get("action") if audits else None,
        }
    )


if __name__ == "__main__":
    main()
