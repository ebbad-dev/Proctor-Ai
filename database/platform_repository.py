from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from core.security import new_id, utc_now
from core.session_lifecycle import (
    SESSION_ACTIVE,
    SESSION_ENDED,
    SESSION_REVIEWED,
    SESSION_SUBMITTED,
    is_active_session,
    is_terminal_session,
    normalize_session_status,
)

DEFAULT_TENANT_ID = "tenant_default"


class PlatformRepository:
    def __init__(self, db):
        self.db = db

    def ensure_default_tenant(self) -> dict:
        rows = self.db.query("SELECT tenant_id, name, slug, status, plan_name, settings_json, created_at FROM Tenants WHERE tenant_id = ?", (DEFAULT_TENANT_ID,))
        if rows:
            return rows[0]
        self.db.execute(
            """
            INSERT INTO Tenants (tenant_id, name, slug, status, plan_name, settings_json)
            VALUES (?, 'Default Institution', 'default', 'active', 'enterprise', '{}')
            """,
            (DEFAULT_TENANT_ID,),
        )
        return self.ensure_default_tenant()

    def list_tenants(self) -> list[dict]:
        return self.db.query(
            """
            SELECT tenant_id, name, slug, status, plan_name, settings_json, created_at, updated_at
            FROM Tenants ORDER BY created_at DESC
            """
        )

    def get_tenant(self, tenant_id: str) -> dict | None:
        rows = self.db.query(
            """
            SELECT tenant_id, name, slug, status, plan_name, settings_json, created_at, updated_at
            FROM Tenants WHERE tenant_id = ?
            """,
            (tenant_id,),
        )
        return rows[0] if rows else None

    def create_tenant(self, name: str, slug: str, plan_name: str = "enterprise", settings: dict | None = None) -> dict:
        tenant_id = new_id("tenant")
        self.db.execute(
            """
            INSERT INTO Tenants (tenant_id, name, slug, status, plan_name, settings_json, created_at)
            VALUES (?, ?, ?, 'active', ?, ?, ?)
            """,
            (tenant_id, name, slug, plan_name or "enterprise", json.dumps(settings or {}), utc_now()),
        )
        return self.get_tenant(tenant_id) or {}

    def update_tenant(self, tenant_id: str, data: dict) -> dict | None:
        current = self.get_tenant(tenant_id)
        if not current:
            return None
        self.db.execute(
            """
            UPDATE Tenants
            SET name = ?, slug = ?, status = ?, plan_name = ?, settings_json = ?, updated_at = ?
            WHERE tenant_id = ?
            """,
            (
                data.get("name", current.get("name")),
                data.get("slug", current.get("slug")),
                data.get("status", current.get("status") or "active"),
                data.get("plan_name", current.get("plan_name") or "enterprise"),
                json.dumps(data.get("settings") if data.get("settings") is not None else _json_load(current.get("settings_json"))),
                utc_now(),
                tenant_id,
            ),
        )
        return self.get_tenant(tenant_id)

    def get_user_by_email(self, email: str) -> dict | None:
        rows = self.db.query(
            """
            SELECT u.user_id, u.tenant_id, t.name AS tenant_name, u.email, u.full_name, u.role,
                   u.password_hash, u.is_active, u.created_at, u.updated_at
            FROM Users u
            LEFT JOIN Tenants t ON t.tenant_id = u.tenant_id
            WHERE LOWER(u.email) = LOWER(?)
            """,
            (email,),
        )
        return rows[0] if rows else None

    def get_user(self, user_id: str) -> dict | None:
        rows = self.db.query(
            """
            SELECT u.user_id, u.tenant_id, t.name AS tenant_name, u.email, u.full_name, u.role,
                   u.password_hash, u.is_active, u.created_at, u.updated_at
            FROM Users u
            LEFT JOIN Tenants t ON t.tenant_id = u.tenant_id
            WHERE u.user_id = ?
            """,
            (user_id,),
        )
        return rows[0] if rows else None

    def public_user(self, user: dict) -> dict:
        return {
            "user_id": user.get("user_id"),
            "email": user.get("email"),
            "full_name": user.get("full_name"),
            "role": user.get("role"),
            "tenant_id": user.get("tenant_id") or DEFAULT_TENANT_ID,
            "tenant_name": user.get("tenant_name") or "Default Institution",
            "is_active": bool(user.get("is_active", True)),
            "created_at": user.get("created_at"),
            "updated_at": user.get("updated_at"),
        }

    def create_user(self, email: str, full_name: str, role: str, password_hash: str, tenant_id: str | None = None) -> dict:
        tenant_id = tenant_id or DEFAULT_TENANT_ID
        user_id = new_id("usr")
        self.db.execute(
            """
            INSERT INTO Users (user_id, tenant_id, email, full_name, role, password_hash, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?)
            """,
            (user_id, tenant_id, email.lower(), full_name, role, password_hash, utc_now()),
        )
        return self.get_user(user_id) or {}

    def admin_count(self) -> int:
        rows = self.db.query("SELECT COUNT(*) AS count FROM Users WHERE role = 'admin'")
        return int(rows[0].get("count") or 0) if rows else 0

    def active_admin_count(self) -> int:
        rows = self.db.query("SELECT COUNT(*) AS count FROM Users WHERE role = 'admin' AND is_active = 1")
        return int(rows[0].get("count") or 0) if rows else 0

    def list_users(
        self,
        *,
        tenant_id: str | None = None,
        role: str = "",
        query: str = "",
        limit: int = 200,
    ) -> list[dict]:
        clauses = []
        params: list[Any] = []
        if tenant_id:
            clauses.append("COALESCE(u.tenant_id, ?) = ?")
            params.extend([tenant_id, tenant_id])
        if role:
            clauses.append("u.role = ?")
            params.append(role)
        if query:
            clauses.append("(LOWER(u.email) LIKE LOWER(?) OR LOWER(u.full_name) LIKE LOWER(?))")
            needle = f"%{query}%"
            params.extend([needle, needle])
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        limit = max(1, min(int(limit or 200), 500))
        return self.db.query(
            f"""
            SELECT TOP {limit}
                u.user_id, u.tenant_id, t.name AS tenant_name, u.email, u.full_name,
                u.role, u.is_active, u.created_at, u.updated_at
            FROM Users u
            LEFT JOIN Tenants t ON t.tenant_id = u.tenant_id
            {where}
            ORDER BY u.created_at DESC
            """,
            tuple(params),
        )

    def update_user(self, user_id: str, data: dict) -> dict | None:
        current = self.get_user(user_id)
        if not current:
            return None
        self.db.execute(
            """
            UPDATE Users
            SET tenant_id = ?, full_name = ?, role = ?, is_active = ?, updated_at = ?
            WHERE user_id = ?
            """,
            (
                data.get("tenant_id") or current.get("tenant_id") or DEFAULT_TENANT_ID,
                data.get("full_name", current.get("full_name")),
                data.get("role", current.get("role")),
                1 if bool(data.get("is_active", current.get("is_active", True))) else 0,
                utc_now(),
                user_id,
            ),
        )
        return self.get_user(user_id)

    def create_reset_token(self, user_id: str, token_hash: str, expires_at: datetime) -> str:
        token_id = new_id("rst")
        self.db.execute(
            """
            INSERT INTO PasswordResetTokens (token_id, user_id, token_hash, expires_at, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (token_id, user_id, token_hash, expires_at, utc_now()),
        )
        return token_id

    def get_reset_token(self, token_hash: str) -> dict | None:
        rows = self.db.query(
            """
            SELECT token_id, user_id, token_hash, expires_at, used_at, created_at
            FROM PasswordResetTokens WHERE token_hash = ?
            """,
            (token_hash,),
        )
        return rows[0] if rows else None

    def mark_reset_token_used(self, token_id: str) -> None:
        self.db.execute(
            "UPDATE PasswordResetTokens SET used_at = ? WHERE token_id = ?",
            (utc_now(), token_id),
        )

    def update_password(self, user_id: str, password_hash: str) -> None:
        self.db.execute(
            "UPDATE Users SET password_hash = ?, updated_at = ? WHERE user_id = ?",
            (password_hash, utc_now(), user_id),
        )

    def list_exams(self, user: dict) -> list[dict]:
        tenant_id = user.get("tenant_id") or DEFAULT_TENANT_ID
        if user["role"] == "student":
            return self.db.query(
                """
                SELECT e.exam_id, e.tenant_id, e.exam_code, e.title, e.description,
                       e.semester, e.subject, e.department, e.total_marks,
                       e.duration_minutes, e.start_time, e.end_time, e.status, e.rules_json,
                       a.assignment_id, a.status AS assignment_status,
                       0 AS assignment_count
                FROM ExamAssignments a
                JOIN Exams e ON e.exam_id = a.exam_id
                WHERE a.student_user_id = ? AND COALESCE(a.tenant_id, ?) = ? AND a.status <> 'revoked'
                ORDER BY COALESCE(e.start_time, e.created_at) DESC
                """,
                (user["user_id"], tenant_id, tenant_id),
            )
        return self.db.query(
            """
            SELECT e.exam_id, e.tenant_id, e.exam_code, e.title, e.description,
                   e.semester, e.subject, e.department, e.total_marks,
                   e.duration_minutes, e.start_time, e.end_time, e.status, e.rules_json,
                   COUNT(CASE WHEN a.status <> 'revoked' THEN 1 END) AS assignment_count
            FROM Exams e
            LEFT JOIN ExamAssignments a ON a.exam_id = e.exam_id
            WHERE COALESCE(e.tenant_id, ?) = ?
            GROUP BY e.exam_id, e.tenant_id, e.exam_code, e.title, e.description,
                     e.semester, e.subject, e.department, e.total_marks, e.duration_minutes,
                     e.start_time, e.end_time, e.status, e.rules_json, e.created_at
            ORDER BY e.created_at DESC
            """,
            (tenant_id, tenant_id),
        )

    def get_exam(self, exam_id: str) -> dict | None:
        rows = self.db.query(
            """
            SELECT e.exam_id, e.tenant_id, e.exam_code, e.title, e.description,
                   e.semester, e.subject, e.department, e.total_marks,
                   e.duration_minutes, e.start_time, e.end_time, e.status, e.rules_json,
                   COUNT(CASE WHEN a.status <> 'revoked' THEN 1 END) AS assignment_count
            FROM Exams e
            LEFT JOIN ExamAssignments a ON a.exam_id = e.exam_id
            WHERE e.exam_id = ?
            GROUP BY e.exam_id, e.tenant_id, e.exam_code, e.title, e.description,
                     e.semester, e.subject, e.department, e.total_marks, e.duration_minutes,
                     e.start_time, e.end_time, e.status, e.rules_json
            """,
            (exam_id,),
        )
        return rows[0] if rows else None

    def get_exam_by_code(self, exam_code: str, tenant_id: str | None = None) -> dict | None:
        rows = self.db.query(
            """
            SELECT e.exam_id, e.tenant_id, e.exam_code, e.title, e.description,
                   e.semester, e.subject, e.department, e.total_marks,
                   e.duration_minutes, e.start_time, e.end_time, e.status, e.rules_json,
                   COUNT(CASE WHEN a.status <> 'revoked' THEN 1 END) AS assignment_count
            FROM Exams e
            LEFT JOIN ExamAssignments a ON a.exam_id = e.exam_id
            WHERE UPPER(e.exam_code) = UPPER(?) AND COALESCE(e.tenant_id, ?) = ?
            GROUP BY e.exam_id, e.tenant_id, e.exam_code, e.title, e.description,
                     e.semester, e.subject, e.department, e.total_marks, e.duration_minutes,
                     e.start_time, e.end_time, e.status, e.rules_json
            """,
            ((exam_code or "").strip(), tenant_id or DEFAULT_TENANT_ID, tenant_id or DEFAULT_TENANT_ID),
        )
        return rows[0] if rows else None

    def create_exam(self, data: dict, created_by: str, tenant_id: str | None = None) -> dict:
        tenant_id = tenant_id or DEFAULT_TENANT_ID
        exam_id = data.get("exam_id") or new_id("exam")
        exam_code = self._available_exam_code(data.get("exam_code") or "")
        self.db.execute(
            """
            INSERT INTO Exams (
                exam_id, tenant_id, exam_code, title, description, semester, subject,
                department, total_marks, duration_minutes, start_time, end_time, status,
                rules_json, created_by, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                exam_id,
                tenant_id,
                exam_code,
                data["title"],
                data.get("description", ""),
                data.get("semester", ""),
                data.get("subject", ""),
                data.get("department", ""),
                int(data.get("total_marks") or 0),
                int(data.get("duration_minutes") or 60),
                data.get("start_time"),
                data.get("end_time"),
                data.get("status", "draft"),
                json.dumps(data.get("rules") or {}),
                created_by,
                utc_now(),
            ),
        )
        return self.get_exam(exam_id) or {}

    def update_exam(self, exam_id: str, data: dict) -> dict | None:
        current = self.get_exam(exam_id)
        if not current:
            return None
        exam_code = data.get("exam_code", current.get("exam_code") or "")
        if exam_code and str(exam_code).upper() != str(current.get("exam_code") or "").upper():
            exam_code = self._available_exam_code(exam_code)
        self.db.execute(
            """
            UPDATE Exams SET exam_code = ?, title = ?, description = ?, semester = ?, subject = ?,
                department = ?, total_marks = ?, duration_minutes = ?, start_time = ?,
                end_time = ?, status = ?, rules_json = ?, updated_at = ?
            WHERE exam_id = ?
            """,
            (
                exam_code,
                data.get("title", current.get("title")),
                data.get("description", current.get("description") or ""),
                data.get("semester", current.get("semester") or ""),
                data.get("subject", current.get("subject") or ""),
                data.get("department", current.get("department") or ""),
                int(data.get("total_marks") if data.get("total_marks") is not None else current.get("total_marks") or 0),
                int(data.get("duration_minutes") or current.get("duration_minutes") or 60),
                data.get("start_time", current.get("start_time")),
                data.get("end_time", current.get("end_time")),
                data.get("status", current.get("status") or "draft"),
                json.dumps(data.get("rules") or _json_load(current.get("rules_json"))),
                utc_now(),
                exam_id,
            ),
        )
        return self.get_exam(exam_id)

    def publish_exam(self, exam_id: str) -> dict | None:
        self.db.execute(
            "UPDATE Exams SET status = 'published', updated_at = ? WHERE exam_id = ?",
            (utc_now(), exam_id),
        )
        return self.get_exam(exam_id)

    def _available_exam_code(self, requested: str) -> str:
        code = "".join(ch for ch in str(requested or "").upper().strip() if ch.isalnum() or ch in "-_")
        if not code:
            code = new_id("EXAM").replace("exam_", "").replace("EXAM_", "")[:8].upper()
        rows = self.db.query("SELECT exam_id FROM Exams WHERE UPPER(exam_code) = UPPER(?)", (code,))
        if not rows:
            return code
        suffix = 2
        base = code[:52]
        while True:
            candidate = f"{base}-{suffix}"
            rows = self.db.query("SELECT exam_id FROM Exams WHERE UPPER(exam_code) = UPPER(?)", (candidate,))
            if not rows:
                return candidate
            suffix += 1

    def list_exam_questions(self, exam_id: str, *, include_correct: bool = False) -> list[dict]:
        questions = self.db.query(
            """
            SELECT question_id, tenant_id, exam_id, question_text, question_type, marks,
                   sort_order, status, created_at, updated_at
            FROM ExamQuestions
            WHERE exam_id = ? AND status <> 'deleted'
            ORDER BY sort_order ASC, created_at ASC
            """,
            (exam_id,),
        )
        for question in questions:
            options = self.db.query(
                """
                SELECT option_id, tenant_id, question_id, option_text, is_correct, sort_order, created_at, updated_at
                FROM QuestionOptions
                WHERE question_id = ?
                ORDER BY sort_order ASC, created_at ASC
                """,
                (question["question_id"],),
            )
            if not include_correct:
                for option in options:
                    option.pop("is_correct", None)
            question["options"] = options
        return questions

    def get_question(self, question_id: str) -> dict | None:
        rows = self.db.query(
            """
            SELECT q.question_id, q.tenant_id, q.exam_id, q.question_text, q.question_type,
                   q.marks, q.sort_order, q.status
            FROM ExamQuestions q
            WHERE q.question_id = ?
            """,
            (question_id,),
        )
        return rows[0] if rows else None

    def upsert_question(self, exam_id: str, data: dict, tenant_id: str | None = None, question_id: str = "") -> dict:
        tenant_id = tenant_id or DEFAULT_TENANT_ID
        question_id = question_id or data.get("question_id") or new_id("qst")
        existing = self.get_question(question_id)
        if existing:
            self.db.execute(
                """
                UPDATE ExamQuestions
                SET question_text = ?, question_type = ?, marks = ?, sort_order = ?, status = ?, updated_at = ?
                WHERE question_id = ?
                """,
                (
                    data.get("question_text", existing.get("question_text")),
                    data.get("question_type", existing.get("question_type") or "mcq"),
                    int(data.get("marks") or existing.get("marks") or 1),
                    int(data.get("sort_order") if data.get("sort_order") is not None else existing.get("sort_order") or 0),
                    data.get("status", existing.get("status") or "active"),
                    utc_now(),
                    question_id,
                ),
            )
        else:
            self.db.execute(
                """
                INSERT INTO ExamQuestions (
                    question_id, tenant_id, exam_id, question_text, question_type, marks, sort_order, status, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    question_id,
                    tenant_id,
                    exam_id,
                    data["question_text"],
                    data.get("question_type") or "mcq",
                    int(data.get("marks") or 1),
                    int(data.get("sort_order") or 0),
                    data.get("status") or "active",
                    utc_now(),
                ),
            )
        if "options" in data:
            self.replace_question_options(question_id, data.get("options") or [], tenant_id)
        return self.get_question(question_id) or {}

    def delete_question(self, question_id: str) -> None:
        self.db.execute(
            "UPDATE ExamQuestions SET status = 'deleted', updated_at = ? WHERE question_id = ?",
            (utc_now(), question_id),
        )

    def replace_question_options(self, question_id: str, options: list[dict], tenant_id: str | None = None) -> None:
        tenant_id = tenant_id or DEFAULT_TENANT_ID
        self.db.execute("DELETE FROM QuestionOptions WHERE question_id = ?", (question_id,))
        for idx, option in enumerate(options):
            text = str(option.get("option_text") or option.get("text") or "").strip()
            if not text:
                continue
            self.db.execute(
                """
                INSERT INTO QuestionOptions (
                    option_id, tenant_id, question_id, option_text, is_correct, sort_order, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    option.get("option_id") or new_id("opt"),
                    tenant_id,
                    question_id,
                    text,
                    1 if bool(option.get("is_correct")) else 0,
                    int(option.get("sort_order") if option.get("sort_order") is not None else idx),
                    utc_now(),
                ),
            )

    def get_option(self, option_id: str) -> dict | None:
        rows = self.db.query(
            """
            SELECT o.option_id, o.tenant_id, o.question_id, o.option_text, o.is_correct, o.sort_order,
                   q.exam_id, q.marks
            FROM QuestionOptions o
            JOIN ExamQuestions q ON q.question_id = o.question_id
            WHERE o.option_id = ?
            """,
            (option_id,),
        )
        return rows[0] if rows else None

    def upsert_option(self, question_id: str, data: dict, tenant_id: str | None = None, option_id: str = "") -> dict:
        tenant_id = tenant_id or DEFAULT_TENANT_ID
        option_id = option_id or data.get("option_id") or new_id("opt")
        existing = self.get_option(option_id)
        if existing:
            self.db.execute(
                """
                UPDATE QuestionOptions
                SET option_text = ?, is_correct = ?, sort_order = ?, updated_at = ?
                WHERE option_id = ?
                """,
                (
                    data.get("option_text", existing.get("option_text")),
                    1 if bool(data.get("is_correct", existing.get("is_correct"))) else 0,
                    int(data.get("sort_order") if data.get("sort_order") is not None else existing.get("sort_order") or 0),
                    utc_now(),
                    option_id,
                ),
            )
        else:
            self.db.execute(
                """
                INSERT INTO QuestionOptions (option_id, tenant_id, question_id, option_text, is_correct, sort_order, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    option_id,
                    tenant_id,
                    question_id,
                    data["option_text"],
                    1 if bool(data.get("is_correct")) else 0,
                    int(data.get("sort_order") or 0),
                    utc_now(),
                ),
            )
        return self.get_option(option_id) or {}

    def delete_option(self, option_id: str) -> None:
        self.db.execute("DELETE FROM QuestionOptions WHERE option_id = ?", (option_id,))

    def assign_exam(self, exam_id: str, student_user_id: str, assigned_by: str, tenant_id: str | None = None) -> dict:
        tenant_id = tenant_id or DEFAULT_TENANT_ID
        rows = self.db.query(
            "SELECT assignment_id, status FROM ExamAssignments WHERE exam_id = ? AND student_user_id = ?",
            (exam_id, student_user_id),
        )
        if rows:
            assignment_id = rows[0]["assignment_id"]
            if rows[0].get("status") == "revoked":
                self.db.execute(
                    "UPDATE ExamAssignments SET status = 'assigned', assigned_by = ?, assigned_at = ? WHERE assignment_id = ?",
                    (assigned_by, utc_now(), assignment_id),
                )
            return {"assignment_id": assignment_id, "exam_id": exam_id, "student_user_id": student_user_id}
        assignment_id = new_id("asg")
        self.db.execute(
            """
            INSERT INTO ExamAssignments (assignment_id, tenant_id, exam_id, student_user_id, assigned_by, assigned_at, status)
            VALUES (?, ?, ?, ?, ?, ?, 'assigned')
            """,
            (assignment_id, tenant_id, exam_id, student_user_id, assigned_by, utc_now()),
        )
        return {"assignment_id": assignment_id, "exam_id": exam_id, "student_user_id": student_user_id}

    def list_exam_assignments(self, exam_id: str) -> list[dict]:
        return self.db.query(
            """
            SELECT a.assignment_id, a.tenant_id, a.exam_id, a.student_user_id, a.assigned_by,
                   a.assigned_at, a.status,
                   u.email AS student_email, u.full_name AS student_name, u.is_active AS student_active
            FROM ExamAssignments a
            JOIN Users u ON u.user_id = a.student_user_id
            WHERE a.exam_id = ?
            ORDER BY a.assigned_at DESC
            """,
            (exam_id,),
        )

    def revoke_assignment(self, assignment_id: str) -> dict | None:
        rows = self.db.query(
            """
            SELECT assignment_id, exam_id, student_user_id, status
            FROM ExamAssignments WHERE assignment_id = ?
            """,
            (assignment_id,),
        )
        if not rows:
            return None
        self.db.execute(
            "UPDATE ExamAssignments SET status = 'revoked' WHERE assignment_id = ?",
            (assignment_id,),
        )
        return {**rows[0], "status": "revoked"}

    def exam_assigned_to_student(self, exam_id: str, user_id: str) -> bool:
        rows = self.db.query(
            "SELECT assignment_id FROM ExamAssignments WHERE exam_id = ? AND student_user_id = ? AND status <> 'revoked'",
            (exam_id, user_id),
        )
        return bool(rows)

    def assignment_for_student(self, exam_id: str, user_id: str) -> dict | None:
        rows = self.db.query(
            """
            SELECT assignment_id, tenant_id, exam_id, student_user_id, assigned_by, assigned_at, status
            FROM ExamAssignments
            WHERE exam_id = ? AND student_user_id = ? AND status <> 'revoked'
            """,
            (exam_id, user_id),
        )
        return rows[0] if rows else None

    def ensure_code_assignment(self, exam_id: str, user_id: str, tenant_id: str | None = None) -> dict:
        existing = self.assignment_for_student(exam_id, user_id)
        if existing:
            return existing
        assignment = self.assign_exam(exam_id, user_id, "exam_code_join", tenant_id or DEFAULT_TENANT_ID)
        return self.assignment_for_student(exam_id, user_id) or assignment

    def submitted_attempt_for_student(self, exam_id: str, user_id: str) -> dict | None:
        rows = self.db.query(
            """
            SELECT TOP 1 attempt_id, tenant_id, exam_id, assignment_id, session_id, user_id,
                   roll_number, status, started_at, submitted_at, score, max_score
            FROM ExamAttempts
            WHERE exam_id = ? AND user_id = ? AND status = 'submitted'
            ORDER BY submitted_at DESC
            """,
            (exam_id, user_id),
        )
        return rows[0] if rows else None

    def active_attempt_for_student(self, exam_id: str, user_id: str) -> dict | None:
        rows = self.db.query(
            """
            SELECT TOP 1 attempt_id, tenant_id, exam_id, assignment_id, session_id, user_id,
                   roll_number, status, started_at, submitted_at, score, max_score
            FROM ExamAttempts
            WHERE exam_id = ? AND user_id = ? AND status = 'in_progress'
            ORDER BY started_at DESC
            """,
            (exam_id, user_id),
        )
        return rows[0] if rows else None

    def active_attempt_for_user(self, user_id: str) -> dict | None:
        rows = self.db.query(
            """
            SELECT TOP 1 a.attempt_id, a.tenant_id, a.exam_id, a.assignment_id, a.session_id,
                   a.user_id, a.roll_number, a.status, a.started_at, a.submitted_at,
                   a.score, a.max_score, e.duration_minutes
            FROM ExamAttempts a
            JOIN Exams e ON e.exam_id = a.exam_id
            WHERE a.user_id = ? AND a.status = 'in_progress'
            ORDER BY a.started_at DESC
            """,
            (user_id,),
        )
        return rows[0] if rows else None

    def create_attempt(
        self,
        *,
        exam_id: str,
        user_id: str,
        roll_number: str,
        assignment_id: str = "",
        session_id: str = "",
        tenant_id: str | None = None,
    ) -> dict:
        tenant_id = tenant_id or DEFAULT_TENANT_ID
        attempt_id = new_id("atm")
        max_score = self.exam_max_score(exam_id)
        self.db.execute(
            """
            INSERT INTO ExamAttempts (
                attempt_id, tenant_id, exam_id, assignment_id, session_id, user_id,
                roll_number, status, started_at, score, max_score, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 'in_progress', ?, 0, ?, ?)
            """,
            (
                attempt_id,
                tenant_id,
                exam_id,
                assignment_id or None,
                session_id or None,
                user_id,
                roll_number,
                utc_now(),
                max_score,
                utc_now(),
            ),
        )
        return self.get_attempt(attempt_id) or {}

    def cancel_attempt_start(self, attempt_id: str) -> bool:
        updated = self.db.execute(
            """
            UPDATE ExamAttempts
            SET status = 'cancelled', updated_at = ?
            WHERE attempt_id = ? AND status = 'in_progress'
              AND NOT EXISTS (
                  SELECT 1 FROM StudentResponses WHERE attempt_id = ?
              )
            """,
            (utc_now(), attempt_id, attempt_id),
        )
        return updated != 0

    def get_attempt(self, attempt_id: str) -> dict | None:
        rows = self.db.query(
            """
            SELECT a.attempt_id, a.tenant_id, a.exam_id, a.assignment_id, a.session_id, a.user_id,
                   a.roll_number, a.status, a.started_at, a.submitted_at, a.score, a.max_score,
                   e.exam_code, e.title AS exam_title, e.duration_minutes, e.total_marks,
                   u.email AS student_email, u.full_name AS student_name
            FROM ExamAttempts a
            JOIN Exams e ON e.exam_id = a.exam_id
            JOIN Users u ON u.user_id = a.user_id
            WHERE a.attempt_id = ?
            """,
            (attempt_id,),
        )
        return rows[0] if rows else None

    def list_attempts_for_exam(self, exam_id: str) -> list[dict]:
        return self.db.query(
            """
            SELECT a.attempt_id, a.tenant_id, a.exam_id, a.assignment_id, a.session_id, a.user_id,
                   a.roll_number, a.status, a.started_at, a.submitted_at, a.score, a.max_score,
                   u.email AS student_email, u.full_name AS student_name,
                   COALESCE(SUM(ev.risk_points), 0) AS risk_score
            FROM ExamAttempts a
            JOIN Users u ON u.user_id = a.user_id
            LEFT JOIN Events ev ON ev.session_id = a.session_id
            WHERE a.exam_id = ?
            GROUP BY a.attempt_id, a.tenant_id, a.exam_id, a.assignment_id, a.session_id, a.user_id,
                     a.roll_number, a.status, a.started_at, a.submitted_at, a.score, a.max_score,
                     u.email, u.full_name
            ORDER BY COALESCE(a.submitted_at, a.started_at) DESC
            """,
            (exam_id,),
        )

    def get_attempt_responses(self, attempt_id: str) -> list[dict]:
        return self.db.query(
            """
            SELECT r.response_id, r.tenant_id, r.attempt_id, r.question_id, r.selected_option_id,
                   r.response_text, r.is_correct, r.awarded_marks, r.answered_at, r.updated_at,
                   q.question_text, q.marks, o.option_text AS selected_option_text
            FROM StudentResponses r
            JOIN ExamQuestions q ON q.question_id = r.question_id
            LEFT JOIN QuestionOptions o ON o.option_id = r.selected_option_id
            WHERE r.attempt_id = ?
            ORDER BY q.sort_order ASC, r.answered_at ASC
            """,
            (attempt_id,),
        )

    def save_response(
        self,
        *,
        attempt_id: str,
        question_id: str,
        selected_option_id: str = "",
        response_text: str = "",
        tenant_id: str | None = None,
    ) -> dict:
        tenant_id = tenant_id or DEFAULT_TENANT_ID
        attempt = self.get_attempt(attempt_id)
        if not attempt:
            return {}
        option = self.get_option(selected_option_id) if selected_option_id else None
        question = self.get_question(question_id)
        is_correct = bool(option and option.get("question_id") == question_id and option.get("is_correct"))
        awarded = int(question.get("marks") or 0) if question and is_correct else 0
        rows = self.db.query(
            "SELECT response_id FROM StudentResponses WHERE attempt_id = ? AND question_id = ?",
            (attempt_id, question_id),
        )
        if rows:
            response_id = rows[0]["response_id"]
            self.db.execute(
                """
                UPDATE StudentResponses
                SET selected_option_id = ?, response_text = ?, is_correct = ?, awarded_marks = ?, updated_at = ?
                WHERE response_id = ?
                """,
                (selected_option_id or None, response_text, 1 if is_correct else 0, awarded, utc_now(), response_id),
            )
        else:
            response_id = new_id("rsp")
            self.db.execute(
                """
                INSERT INTO StudentResponses (
                    response_id, tenant_id, attempt_id, question_id, selected_option_id,
                    response_text, is_correct, awarded_marks, answered_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    response_id,
                    tenant_id,
                    attempt_id,
                    question_id,
                    selected_option_id or None,
                    response_text,
                    1 if is_correct else 0,
                    awarded,
                    utc_now(),
                ),
            )
        return self.db.query(
            """
            SELECT response_id, tenant_id, attempt_id, question_id, selected_option_id,
                   response_text, is_correct, awarded_marks, answered_at, updated_at
            FROM StudentResponses WHERE response_id = ?
            """,
            (response_id,),
        )[0]

    def submit_attempt(self, attempt_id: str) -> dict | None:
        attempt = self.get_attempt(attempt_id)
        if not attempt:
            return None
        if attempt.get("status") == "submitted":
            if attempt.get("session_id"):
                self.db.execute(
                    """
                    UPDATE Sessions
                    SET status = CASE WHEN status = ? THEN status ELSE ? END,
                        end_time = COALESCE(end_time, ?, ?),
                        final_score = COALESCE(final_score, ?)
                    WHERE session_id = ?
                      AND status IN ('Active', 'Submitted', 'Completed', 'Reviewed')
                    """,
                    (
                        SESSION_REVIEWED,
                        SESSION_SUBMITTED,
                        attempt.get("submitted_at"),
                        utc_now(),
                        int(attempt.get("score") or 0),
                        attempt["session_id"],
                    ),
                )
            return {**attempt, "idempotent_replay": True}
        if attempt.get("status") != "in_progress":
            raise ValueError(f"Cannot submit attempt in state {attempt.get('status') or 'unknown'}")
        responses = self.get_attempt_responses(attempt_id)
        score = sum(int(row.get("awarded_marks") or 0) for row in responses)
        max_score = self.exam_max_score(attempt["exam_id"])
        submitted_at = utc_now()
        updated = self.db.execute(
            """
            UPDATE ExamAttempts
            SET status = 'submitted', submitted_at = ?, score = ?, max_score = ?, updated_at = ?
            WHERE attempt_id = ? AND status = 'in_progress'
            """,
            (submitted_at, score, max_score, submitted_at, attempt_id),
        )
        if updated == 0:
            current = self.get_attempt(attempt_id)
            if current and current.get("status") == "submitted":
                return {**current, "idempotent_replay": True}
            raise RuntimeError("Attempt state changed while it was submitting")
        if attempt.get("session_id"):
            self.db.execute(
                """
                UPDATE Sessions
                SET status = CASE WHEN status = ? THEN status ELSE ? END,
                    end_time = COALESCE(end_time, ?),
                    final_score = ?
                WHERE session_id = ?
                  AND status IN ('Active', 'Submitted', 'Completed', 'Reviewed')
                """,
                (SESSION_REVIEWED, SESSION_SUBMITTED, submitted_at, score, attempt["session_id"]),
            )
        submitted = self.get_attempt(attempt_id)
        return {**submitted, "idempotent_replay": False} if submitted else None

    def exam_max_score(self, exam_id: str) -> int:
        rows = self.db.query(
            "SELECT COALESCE(SUM(marks), 0) AS score FROM ExamQuestions WHERE exam_id = ? AND status <> 'deleted'",
            (exam_id,),
        )
        score = int(rows[0].get("score") or 0) if rows else 0
        if score:
            return score
        exam = self.get_exam(exam_id)
        return int(exam.get("total_marks") or 0) if exam else 0

    def exam_attendance(self, exam_id: str) -> list[dict]:
        return self.db.query(
            """
            SELECT
                a.assignment_id,
                a.exam_id,
                a.student_user_id,
                a.status AS assignment_status,
                u.email AS student_email,
                u.full_name AS student_name,
                latest.attempt_id,
                latest.session_id,
                latest.roll_number,
                latest.status AS attempt_status,
                latest.started_at,
                latest.submitted_at,
                latest.score,
                latest.max_score,
                COALESCE(risk.risk_score, 0) AS risk_score
            FROM ExamAssignments a
            JOIN Users u ON u.user_id = a.student_user_id
            OUTER APPLY (
                SELECT TOP 1 attempt_id, session_id, roll_number, status, started_at,
                       submitted_at, score, max_score
                FROM ExamAttempts ea
                WHERE ea.exam_id = a.exam_id AND ea.user_id = a.student_user_id
                ORDER BY COALESCE(ea.submitted_at, ea.started_at) DESC
            ) latest
            OUTER APPLY (
                SELECT COALESCE(SUM(risk_points), 0) AS risk_score
                FROM Events ev
                WHERE ev.session_id = latest.session_id
            ) risk
            WHERE a.exam_id = ? AND a.status <> 'revoked'
            ORDER BY u.full_name ASC
            """,
            (exam_id,),
        )

    def end_session(self, session_id: str) -> dict | None:
        rows = self.db.query(
            "SELECT session_id, status, end_time FROM Sessions WHERE session_id = ?",
            (session_id,),
        )
        if not rows:
            return None
        status = normalize_session_status(rows[0].get("status"))
        if is_terminal_session(status):
            return {
                "session_id": session_id,
                "status": status,
                "end_time": rows[0].get("end_time"),
                "idempotent_replay": True,
            }
        if not is_active_session(status):
            raise ValueError(f"Cannot end session in state {status or 'unknown'}")
        ended_at = utc_now()
        updated = self.db.execute(
            """
            UPDATE Sessions
            SET status = ?, end_time = COALESCE(end_time, ?)
            WHERE session_id = ? AND status = ?
            """,
            (SESSION_ENDED, ended_at, session_id, SESSION_ACTIVE),
        )
        if updated == 0:
            current = self.db.query(
                "SELECT session_id, status, end_time FROM Sessions WHERE session_id = ?",
                (session_id,),
            )
            if current and is_terminal_session(current[0].get("status")):
                return {
                    "session_id": session_id,
                    "status": normalize_session_status(current[0].get("status")),
                    "end_time": current[0].get("end_time"),
                    "idempotent_replay": True,
                }
            raise RuntimeError("Session state changed while it was ending")
        return {
            "session_id": session_id,
            "status": SESSION_ENDED,
            "end_time": ended_at,
            "idempotent_replay": False,
        }

    def insert_evidence(
        self,
        session_id: str,
        user_id: str,
        evidence_type: str,
        label: str,
        filepath: str,
        tenant_id: str | None = None,
        metadata: dict | None = None,
    ) -> dict:
        tenant_id = tenant_id or self.tenant_for_session(session_id) or DEFAULT_TENANT_ID
        metadata = metadata or {}
        evidence_id = new_id("evd")
        self.db.execute(
            """
            INSERT INTO Evidence (
                evidence_id, tenant_id, session_id, user_id, evidence_type, label, filepath,
                confidence, model_name, detection_class, bounding_box_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                evidence_id,
                tenant_id,
                session_id,
                user_id,
                evidence_type,
                label,
                filepath,
                metadata.get("confidence"),
                metadata.get("model_name", ""),
                metadata.get("detection_class", ""),
                json.dumps(metadata.get("bounding_box") or metadata.get("bounding_box_json") or {}),
                utc_now(),
            ),
        )
        return {"evidence_id": evidence_id, "session_id": session_id, "type": evidence_type, "label": label, "filepath": filepath}

    def get_settings(self, tenant_id: str | None = None) -> dict:
        tenant_id = tenant_id or DEFAULT_TENANT_ID
        rows = self.db.query(
            """
            SELECT setting_key, setting_value
            FROM AppSettings
            WHERE COALESCE(tenant_id, ?) = ? OR setting_key LIKE ?
            """,
            (tenant_id, tenant_id, f"{tenant_id}:%"),
        )
        out = {}
        for row in rows:
            key = str(row["setting_key"])
            if key.startswith(f"{tenant_id}:"):
                key = key.split(":", 1)[1]
            out[key] = _json_load(row["setting_value"])
        return out

    def save_settings(self, values: dict, user_id: str, tenant_id: str | None = None) -> dict:
        tenant_id = tenant_id or DEFAULT_TENANT_ID
        for key, value in values.items():
            storage_key = key if tenant_id == DEFAULT_TENANT_ID else f"{tenant_id}:{key}"
            payload = json.dumps(value)
            self.db.execute(
                """
                MERGE AppSettings AS target
                USING (SELECT ? AS setting_key) AS source
                ON target.setting_key = source.setting_key
                WHEN MATCHED THEN UPDATE SET setting_value = ?, updated_by = ?, updated_at = ?
                WHEN NOT MATCHED THEN INSERT (tenant_id, setting_key, setting_value, updated_by, updated_at)
                    VALUES (?, ?, ?, ?, ?);
                """,
                (storage_key, payload, user_id, utc_now(), tenant_id, storage_key, payload, user_id, utc_now()),
            )
        return self.get_settings(tenant_id)

    def dashboard_metrics(self, tenant_id: str | None = None) -> dict:
        tenant_id = tenant_id or DEFAULT_TENANT_ID
        sessions = self.db.query("SELECT COUNT(*) AS count FROM Sessions WHERE COALESCE(tenant_id, ?) = ?", (tenant_id, tenant_id))
        users = self.db.query("SELECT COUNT(*) AS count FROM Users WHERE COALESCE(tenant_id, ?) = ?", (tenant_id, tenant_id))
        exams = self.db.query("SELECT COUNT(*) AS count FROM Exams WHERE COALESCE(tenant_id, ?) = ?", (tenant_id, tenant_id))
        events = self.db.query("SELECT COUNT(*) AS count FROM Events WHERE COALESCE(tenant_id, ?) = ?", (tenant_id, tenant_id))
        high = self.db.query(
            """
            SELECT COUNT(*) AS count FROM (
                SELECT session_id, SUM(risk_points) AS risk
                FROM Events
                WHERE COALESCE(tenant_id, ?) = ?
                GROUP BY session_id HAVING SUM(risk_points) >= 60
            ) x
            """,
            (tenant_id, tenant_id),
        )
        recent = self.db.query(
            """
            SELECT TOP 12 event_type, session_id, event_time, risk_points, notes
            FROM Events
            WHERE COALESCE(tenant_id, ?) = ?
            ORDER BY event_time DESC
            """,
            (tenant_id, tenant_id),
        )
        return {
            "total_sessions": _count(sessions),
            "total_users": _count(users),
            "total_exams": _count(exams),
            "total_events": _count(events),
            "high_risk_sessions": _count(high),
            "recent_activity": recent,
        }

    def tenant_for_session(self, session_id: str) -> str | None:
        rows = self.db.query("SELECT tenant_id FROM Sessions WHERE session_id = ?", (session_id,))
        return str(rows[0].get("tenant_id")) if rows and rows[0].get("tenant_id") else None

    def write_audit_log(
        self,
        action: str,
        *,
        actor: dict | None = None,
        tenant_id: str | None = None,
        resource_type: str = "",
        resource_id: str = "",
        ip_address: str = "",
        user_agent: str = "",
        details: dict | None = None,
    ) -> dict:
        audit_id = new_id("aud")
        actor = actor or {}
        tenant_id = tenant_id or actor.get("tenant_id") or DEFAULT_TENANT_ID
        self.db.execute(
            """
            INSERT INTO AuditLogs (
                audit_id, tenant_id, actor_user_id, actor_email, actor_role, action,
                resource_type, resource_id, ip_address, user_agent, details_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                audit_id,
                tenant_id,
                actor.get("user_id"),
                actor.get("email"),
                actor.get("role"),
                action,
                resource_type,
                resource_id,
                ip_address,
                user_agent[:512] if user_agent else "",
                json.dumps(details or {}),
                utc_now(),
            ),
        )
        return {"audit_id": audit_id, "action": action, "resource_type": resource_type, "resource_id": resource_id}

    def list_audit_logs(self, tenant_id: str | None = None, limit: int = 100) -> list[dict]:
        tenant_id = tenant_id or DEFAULT_TENANT_ID
        limit = max(1, min(int(limit or 100), 500))
        return self.db.query(
            f"""
            SELECT TOP {limit}
                audit_id, tenant_id, actor_user_id, actor_email, actor_role, action,
                resource_type, resource_id, ip_address, user_agent, details_json, created_at
            FROM AuditLogs
            WHERE COALESCE(tenant_id, ?) = ?
            ORDER BY created_at DESC
            """,
            (tenant_id, tenant_id),
        )


def _count(rows: list[dict]) -> int:
    return int(rows[0].get("count") or 0) if rows else 0


def _json_load(value: Any) -> Any:
    if value in (None, ""):
        return {}
    try:
        return json.loads(str(value))
    except Exception:
        return value
