from __future__ import annotations

import json
import os
import secrets
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if len(os.environ.get("AUTH_SECRET", "")) < 32:
    os.environ["AUTH_SECRET"] = secrets.token_urlsafe(48)

from fastapi.testclient import TestClient

from core.security import create_access_token, hash_password
from database.db_connection import DatabaseConnection
from database.platform_repository import PlatformRepository
from database.student_repository import StudentRepository
from infrastructure.api import fastapi_app as api


def _expect(response, status_code: int, label: str) -> None:
    if response.status_code != status_code:
        raise RuntimeError(
            f"{label}: expected HTTP {status_code}, got {response.status_code}: {response.text[:300]}"
        )


def main() -> int:
    marker = uuid.uuid4().hex
    db = DatabaseConnection()
    if not db.connect(max_retries=1):
        raise SystemExit("SQL Server connection failed")
    repo = PlatformRepository(db)
    student_repo = StudentRepository(db)
    tenant_ids: list[str] = []
    user_ids: list[str] = []
    exam_ids: list[str] = []
    session_ids: list[str] = []
    assignment_ids: list[str] = []

    def cleanup() -> None:
        for session_id in session_ids:
            db.execute("DELETE FROM Events WHERE session_id = ?", (session_id,))
            db.execute("DELETE FROM BrowserActivity WHERE session_id = ?", (session_id,))
            db.execute("DELETE FROM Sessions WHERE session_id = ?", (session_id,))
        for assignment_id in assignment_ids:
            db.execute("DELETE FROM ExamAssignments WHERE assignment_id = ?", (assignment_id,))
        for exam_id in exam_ids:
            db.execute("DELETE FROM Exams WHERE exam_id = ?", (exam_id,))
        for user_id in user_ids:
            db.execute("DELETE FROM AuditLogs WHERE actor_user_id = ?", (user_id,))
            db.execute("DELETE FROM Users WHERE user_id = ?", (user_id,))
        for tenant_id in tenant_ids:
            db.execute("DELETE FROM Tenants WHERE tenant_id = ?", (tenant_id,))

    try:
        tenant_a = repo.create_tenant("Integration Tenant A", f"integration-a-{marker}")
        tenant_ids.append(tenant_a["tenant_id"])
        tenant_b = repo.create_tenant("Integration Tenant B", f"integration-b-{marker}")
        tenant_ids.append(tenant_b["tenant_id"])
        ephemeral_hash = hash_password(f"Temp-{marker}-Aa1!")
        instructor_a = repo.create_user(
            f"instructor-a-{marker}@example.invalid",
            "Integration Instructor A",
            "instructor",
            ephemeral_hash,
            tenant_a["tenant_id"],
        )
        user_ids.append(instructor_a["user_id"])
        instructor_b = repo.create_user(
            f"instructor-b-{marker}@example.invalid",
            "Integration Instructor B",
            "instructor",
            ephemeral_hash,
            tenant_b["tenant_id"],
        )
        user_ids.append(instructor_b["user_id"])
        student_a = repo.create_user(
            f"student-a-{marker}@example.invalid",
            "Integration Student A",
            "student",
            ephemeral_hash,
            tenant_a["tenant_id"],
        )
        user_ids.append(student_a["user_id"])
        exam_a = repo.create_exam(
            {"title": "Integration Exam A", "duration_minutes": 30, "status": "draft"},
            instructor_a["user_id"],
            tenant_a["tenant_id"],
        )
        exam_ids.append(exam_a["exam_id"])
        exam_b = repo.create_exam(
            {"title": "Integration Exam B", "duration_minutes": 30, "status": "draft"},
            instructor_b["user_id"],
            tenant_b["tenant_id"],
        )
        exam_ids.append(exam_b["exam_id"])
        assignment = repo.assign_exam(
            exam_a["exam_id"],
            student_a["user_id"],
            instructor_a["user_id"],
            tenant_a["tenant_id"],
        )
        assignment_ids.append(assignment["assignment_id"])
        session_a = f"api_integration_a_{marker}"
        session_b = f"api_integration_b_{marker}"
        session_ids.extend((session_a, session_b))
        student_repo.upsert_session(
            session_a,
            student_id=student_a["user_id"],
            student_name=student_a["full_name"],
            user_id=student_a["user_id"],
            exam_id=exam_a["exam_id"],
            exam_code=exam_a["exam_code"],
            tenant_id=tenant_a["tenant_id"],
            status="Active",
        )
        student_repo.upsert_session(
            session_b,
            student_id=instructor_b["user_id"],
            student_name="Tenant B Session",
            user_id=instructor_b["user_id"],
            exam_id=exam_b["exam_id"],
            exam_code=exam_b["exam_code"],
            tenant_id=tenant_b["tenant_id"],
            status="Ended",
        )

        headers_a = {"Authorization": f"Bearer {create_access_token(instructor_a)}"}
        headers_b = {"Authorization": f"Bearer {create_access_token(instructor_b)}"}
        student_headers = {"Authorization": f"Bearer {create_access_token(student_a)}"}
        with TestClient(api.app) as client:
            health = client.get("/health")
            _expect(health, 200, "anonymous health")
            exams_a = client.get("/exams", headers=headers_a)
            _expect(exams_a, 200, "tenant A exam list")
            visible_exam_ids = {row["exam_id"] for row in exams_a.json()}
            if exam_a["exam_id"] not in visible_exam_ids or exam_b["exam_id"] in visible_exam_ids:
                raise RuntimeError("Instructor exam list crossed tenant boundaries")
            _expect(client.get(f"/exams/{exam_b['exam_id']}", headers=headers_a), 403, "cross-tenant exam A to B")
            _expect(client.get(f"/exams/{exam_a['exam_id']}", headers=headers_b), 403, "cross-tenant exam B to A")
            sessions_a = client.get("/sessions", headers=headers_a)
            _expect(sessions_a, 200, "tenant A session list")
            visible_session_ids = {row["session_id"] for row in sessions_a.json()}
            if session_a not in visible_session_ids or session_b in visible_session_ids:
                raise RuntimeError("Instructor session list crossed tenant boundaries")
            _expect(client.get(f"/sessions/{session_b}", headers=headers_a), 403, "cross-tenant session")
            _expect(client.get(f"/sessions/{session_a}", headers=student_headers), 200, "student-owned session")
            _expect(client.get(f"/sessions/{session_b}", headers=student_headers), 403, "student foreign session")
            _expect(client.get(f"/exams/{exam_a['exam_id']}", headers=student_headers), 200, "assigned student exam")
            _expect(client.get("/ops/status", headers=student_headers), 403, "student operations access")
            ops = client.get("/ops/status", headers=headers_a)
            _expect(ops, 200, "instructor operations access")
            if not ops.json().get("database", {}).get("migrations", {}).get("ready"):
                raise RuntimeError("Operations status did not report ready database migrations")
            _expect(client.get("/ops/metrics", headers=headers_a), 403, "instructor admin metrics access")

        result = {
            "connected": True,
            "health": True,
            "tenant_exam_isolation": True,
            "tenant_session_isolation": True,
            "student_ownership_enforced": True,
            "role_boundaries_enforced": True,
            "migrations_reported_ready": True,
        }
        cleanup()
        remaining = db.query(
            """
            SELECT
                (SELECT COUNT(*) FROM Users WHERE user_id IN (?, ?, ?)) AS users,
                (SELECT COUNT(*) FROM Exams WHERE exam_id IN (?, ?)) AS exams,
                (SELECT COUNT(*) FROM Sessions WHERE session_id IN (?, ?)) AS sessions
            """,
            (
                instructor_a["user_id"],
                instructor_b["user_id"],
                student_a["user_id"],
                exam_a["exam_id"],
                exam_b["exam_id"],
                session_a,
                session_b,
            ),
        )
        result["cleanup_verified"] = bool(
            remaining
            and int(remaining[0].get("users") or 0) == 0
            and int(remaining[0].get("exams") or 0) == 0
            and int(remaining[0].get("sessions") or 0) == 0
        )
        print(json.dumps(result, sort_keys=True))
        return 0 if result["cleanup_verified"] else 1
    finally:
        try:
            cleanup()
        except Exception:
            pass
        app_db = getattr(api, "_db_connection", None)
        if app_db:
            try:
                app_db.close()
            except Exception:
                pass
            api._db_connection = None
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
