from __future__ import annotations

import secrets
from datetime import UTC, datetime

from core.security import hash_password, new_id
from core.session_lifecycle import SESSION_ENDED
from database.db_connection import DatabaseConnection
from database.platform_repository import PlatformRepository
from database.student_repository import StudentRepository


def main() -> int:
    db = DatabaseConnection()
    if not db.connect(max_retries=1):
        raise SystemExit("SQL Server connection failed")

    repo = PlatformRepository(db)
    student_repo = StudentRepository(db)
    tenant = repo.ensure_default_tenant()

    suffix = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    session_id = new_id("smoke_session")
    user_ids: list[str] = []
    exam_ids: list[str] = []
    assignment_ids: list[str] = []

    def cleanup() -> None:
        db.execute("DELETE FROM Events WHERE session_id = ?", (session_id,))
        db.execute("DELETE FROM BrowserActivity WHERE session_id = ?", (session_id,))
        db.execute("DELETE FROM Sessions WHERE session_id = ?", (session_id,))
        db.execute("DELETE FROM AuditLogs WHERE resource_id = ?", (session_id,))
        for assignment_id in assignment_ids:
            db.execute("DELETE FROM ExamAssignments WHERE assignment_id = ?", (assignment_id,))
        for exam_id in exam_ids:
            db.execute("DELETE FROM AuditLogs WHERE resource_id = ?", (exam_id,))
            db.execute("DELETE FROM Exams WHERE exam_id = ?", (exam_id,))
        for user_id in user_ids:
            db.execute("DELETE FROM AuditLogs WHERE actor_user_id = ?", (user_id,))
            db.execute("DELETE FROM Users WHERE user_id = ?", (user_id,))

    try:
        instructor = repo.create_user(
            f"smoke.instructor.{suffix}@proctorai.local",
            "Smoke Instructor",
            "instructor",
            hash_password(secrets.token_urlsafe(32)),
            tenant["tenant_id"],
        )
        user_ids.append(instructor["user_id"])
        student = repo.create_user(
            f"smoke.student.{suffix}@proctorai.local",
            "Smoke Student",
            "student",
            hash_password(secrets.token_urlsafe(32)),
            tenant["tenant_id"],
        )
        user_ids.append(student["user_id"])
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
        exam_ids.append(exam["exam_id"])
        assignment = repo.assign_exam(exam["exam_id"], student["user_id"], instructor["user_id"], tenant["tenant_id"])
        assignment_ids.append(assignment["assignment_id"])

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

        cleanup()
        leftover = db.query(
            """
            SELECT
                (SELECT COUNT(*) FROM Sessions WHERE session_id = ?) AS session_rows,
                (SELECT COUNT(*) FROM Events WHERE session_id = ?) AS event_rows,
                (SELECT COUNT(*) FROM Exams WHERE exam_id = ?) AS exam_rows,
                (SELECT COUNT(*) FROM Users WHERE user_id IN (?, ?)) AS user_rows
            """,
            (session_id, session_id, exam["exam_id"], instructor["user_id"], student["user_id"]),
        )
        cleanup_verified = bool(leftover) and all(int(value or 0) == 0 for value in leftover[0].values())

        result = {
            "connected": True,
            "tenant": tenant["tenant_id"],
            "session_status": session.get("status") if session else None,
            "event_count": len(events),
            "risk_score": session.get("final_score") if session else None,
            "latest_audit_action": audits[0].get("action") if audits else None,
            "cleanup_verified": cleanup_verified,
        }
        print(result)
        passed = bool(
            session
            and session.get("status") == SESSION_ENDED
            and len(events) == 1
            and result["latest_audit_action"] == "smoke.sql_server.completed"
            and cleanup_verified
        )
        return 0 if passed else 1
    finally:
        try:
            cleanup()
        except Exception as exc:  # pragma: no cover - cleanup must not mask the primary result
            print({"cleanup_error": type(exc).__name__})


if __name__ == "__main__":
    raise SystemExit(main())
