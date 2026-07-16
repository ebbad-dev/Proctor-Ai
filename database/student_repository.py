from __future__ import annotations

from datetime import datetime
from typing import Any


class StudentRepository:
    def __init__(self, db):
        self.db = db

    def _tenant_for_session(self, session_id: str) -> str:
        rows = self.db.query("SELECT tenant_id FROM Sessions WHERE session_id = ?", (session_id,))
        if rows and rows[0].get("tenant_id"):
            return str(rows[0]["tenant_id"])
        return "tenant_default"

    def upsert_session(
        self,
        session_id: str,
        student_id: str = "",
        student_name: str = "",
        exam_code: str = "",
        user_id: str = "",
        exam_id: str = "",
        roll_number: str = "",
        tenant_id: str = "",
        start_time: Any = None,
        status: str = "Active",
    ) -> None:
        start_time = start_time or datetime.now()
        insert_tenant_id = tenant_id or "tenant_default"
        self.db.execute(
            """
            MERGE Sessions AS target
            USING (SELECT ? AS session_id) AS source
            ON target.session_id = source.session_id
            WHEN MATCHED THEN UPDATE SET
                student_id = COALESCE(NULLIF(?, ''), target.student_id),
                student_name = COALESCE(NULLIF(?, ''), target.student_name),
                exam_code = COALESCE(NULLIF(?, ''), target.exam_code),
                roll_number = COALESCE(NULLIF(?, ''), target.roll_number),
                user_id = COALESCE(NULLIF(?, ''), target.user_id),
                exam_id = COALESCE(NULLIF(?, ''), target.exam_id),
                tenant_id = COALESCE(NULLIF(?, ''), target.tenant_id),
                status = ?
            WHEN NOT MATCHED THEN INSERT
                (session_id, tenant_id, user_id, exam_id, student_id, student_name, roll_number, exam_code, start_time, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                session_id,
                student_id,
                student_name,
                exam_code,
                roll_number,
                user_id,
                exam_id,
                tenant_id,
                status,
                session_id,
                insert_tenant_id,
                user_id,
                exam_id,
                student_id,
                student_name,
                roll_number,
                exam_code,
                start_time,
                status,
            ),
        )

    def insert_event(
        self,
        session_id: str,
        student_id: str,
        event_type: str,
        event_time: Any,
        risk_points: int,
        notes: str,
        tenant_id: str = "",
        confidence: float | None = None,
        model_name: str = "",
        detection_class: str = "",
        bounding_box_json: str = "",
        evidence_id: str = "",
    ) -> None:
        tenant_id = tenant_id or self._tenant_for_session(session_id)
        self.db.execute(
            """
            INSERT INTO Events (
                tenant_id, session_id, student_id, event_type, event_time, risk_points,
                confidence, model_name, detection_class, bounding_box_json, evidence_id, notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tenant_id,
                session_id,
                student_id,
                event_type,
                event_time,
                risk_points,
                confidence,
                model_name,
                detection_class,
                bounding_box_json,
                evidence_id,
                notes,
            ),
        )

    def get_all_sessions(self) -> list[dict]:
        return self.db.query(
            """
            SELECT
                s.session_id,
                s.tenant_id,
                s.user_id,
                s.exam_id,
                s.student_id,
                s.student_name,
                s.roll_number,
                s.exam_code,
                s.start_time,
                s.end_time,
                COALESCE(s.status, 'Completed') AS status,
                COALESCE(s.final_score, SUM(COALESCE(e.risk_points, 0))) AS final_score,
                s.review_mark,
                s.instructor_notes
            FROM Sessions s
            LEFT JOIN Events e ON e.session_id = s.session_id
            GROUP BY s.session_id, s.tenant_id, s.user_id, s.exam_id, s.student_id, s.student_name, s.roll_number, s.exam_code, s.start_time,
                     s.end_time, s.status, s.final_score, s.review_mark, s.instructor_notes
            ORDER BY s.start_time DESC
            """
        )

    def get_session(self, session_id: str) -> dict | None:
        rows = self.db.query(
            """
            SELECT
                s.session_id,
                s.tenant_id,
                s.user_id,
                s.exam_id,
                s.student_id,
                s.student_name,
                s.roll_number,
                s.exam_code,
                s.start_time,
                s.end_time,
                COALESCE(s.status, 'Completed') AS status,
                COALESCE(s.final_score, SUM(COALESCE(e.risk_points, 0))) AS final_score,
                s.review_mark,
                s.instructor_notes
            FROM Sessions s
            LEFT JOIN Events e ON e.session_id = s.session_id
            WHERE s.session_id = ?
            GROUP BY s.session_id, s.tenant_id, s.user_id, s.exam_id, s.student_id, s.student_name, s.roll_number, s.exam_code, s.start_time,
                     s.end_time, s.status, s.final_score, s.review_mark, s.instructor_notes
            """,
            (session_id,),
        )
        return rows[0] if rows else None

    def get_events(self, session_id: str) -> list[dict]:
        return self.db.query(
            """
            SELECT event_id, tenant_id, session_id, student_id, event_type, event_time, risk_points,
                   confidence, model_name, detection_class, bounding_box_json, evidence_id, notes
            FROM Events
            WHERE session_id = ?
            ORDER BY event_time ASC
            """,
            (session_id,),
        )

    def update_session_review(self, session_id: str, review_mark: str, instructor_notes: str) -> None:
        self.db.execute(
            """
            UPDATE Sessions
            SET review_mark = ?, instructor_notes = ?
            WHERE session_id = ?
            """,
            (review_mark, instructor_notes, session_id),
        )
