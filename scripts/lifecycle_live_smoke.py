from __future__ import annotations

import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database.db_connection import DatabaseConnection
from database.platform_repository import PlatformRepository
from database.student_repository import StudentRepository


def main() -> int:
    db = DatabaseConnection()
    if not db.connect(max_retries=1):
        raise SystemExit("SQL Server connection failed")
    marker = uuid.uuid4().hex
    attempt_one = f"lifecycle_one_{marker}"
    attempt_two = f"lifecycle_two_{marker}"
    user_id = f"lifecycle_user_{marker}"
    session_id = f"lifecycle_session_{marker}"

    def cleanup() -> None:
        db.execute("DELETE FROM Events WHERE session_id = ?", (session_id,))
        db.execute("DELETE FROM BrowserActivity WHERE session_id = ?", (session_id,))
        db.execute("DELETE FROM Sessions WHERE session_id = ?", (session_id,))
        db.execute("DELETE FROM ExamAttempts WHERE attempt_id IN (?, ?)", (attempt_one, attempt_two))

    try:
        conflicts = db.query(
            """
            SELECT user_id, COUNT(*) AS active_count
            FROM ExamAttempts
            WHERE status = 'in_progress'
            GROUP BY user_id
            HAVING COUNT(*) > 1
            """
        )
        indexes = db.query(
            """
            SELECT name
            FROM sys.indexes
            WHERE object_id = OBJECT_ID('ExamAttempts')
              AND name = 'UX_ExamAttempts_ActiveUser'
            """
        )
        if conflicts or not indexes:
            print({
                "connected": True,
                "parallel_active_attempt_conflicts": len(conflicts),
                "active_attempt_unique_index": bool(indexes),
            })
            return 1
        insert_sql = """
            INSERT INTO ExamAttempts (
                attempt_id, tenant_id, exam_id, user_id, roll_number, status,
                started_at, score, max_score, created_at
            )
            VALUES (?, 'tenant_default', ?, ?, 'SMOKE', 'in_progress',
                    SYSUTCDATETIME(), 0, 0, SYSUTCDATETIME())
        """
        db.execute(insert_sql, (attempt_one, f"exam_one_{marker}", user_id))
        duplicate_rejected = False
        try:
            db.execute(insert_sql, (attempt_two, f"exam_two_{marker}", user_id))
        except Exception:
            duplicate_rejected = True
        rows = db.query(
            "SELECT COUNT(*) AS row_count FROM ExamAttempts WHERE user_id = ? AND status = 'in_progress'",
            (user_id,),
        )
        active_count = int(rows[0].get("row_count") or 0) if rows else 0
        db.execute(
            """
            INSERT INTO Sessions (
                session_id, tenant_id, user_id, student_id, student_name,
                exam_code, start_time, status
            )
            VALUES (?, 'tenant_default', ?, ?, 'Lifecycle Smoke',
                    'LIFECYCLE-SMOKE', SYSUTCDATETIME(), 'Active')
            """,
            (session_id, user_id, user_id),
        )
        student_repo = StudentRepository(db)
        active_event_inserted = student_repo.insert_event(
            session_id,
            user_id,
            "Lifecycle Smoke",
            datetime.now(timezone.utc),
            1,
            "Controlled active-session event",
            tenant_id="tenant_default",
            ingest_id=f"active_{marker}",
        )
        platform_repo = PlatformRepository(db)
        first_end = platform_repo.end_session(session_id)
        first_end_rows = db.query("SELECT end_time FROM Sessions WHERE session_id = ?", (session_id,))
        repeated_end = platform_repo.end_session(session_id)
        repeated_end_rows = db.query("SELECT end_time FROM Sessions WHERE session_id = ?", (session_id,))
        late_event_inserted = student_repo.insert_event(
            session_id,
            user_id,
            "Lifecycle Late Smoke",
            datetime.now(timezone.utc),
            1,
            "This row must not be inserted",
            tenant_id="tenant_default",
            ingest_id=f"late_{marker}",
        )
        event_rows = db.query(
            "SELECT COUNT(*) AS row_count FROM Events WHERE session_id = ?",
            (session_id,),
        )
        event_count = int(event_rows[0].get("row_count") or 0) if event_rows else 0
        end_time_stable = bool(
            first_end_rows
            and repeated_end_rows
            and first_end_rows[0].get("end_time") == repeated_end_rows[0].get("end_time")
        )
        cleanup()
        cleanup_rows = db.query(
            """
            SELECT
                (SELECT COUNT(*) FROM ExamAttempts WHERE attempt_id IN (?, ?)) AS attempt_rows,
                (SELECT COUNT(*) FROM Sessions WHERE session_id = ?) AS session_rows,
                (SELECT COUNT(*) FROM Events WHERE session_id = ?) AS event_rows
            """,
            (attempt_one, attempt_two, session_id, session_id),
        )
        cleanup_verified = bool(
            cleanup_rows
            and int(cleanup_rows[0].get("attempt_rows") or 0) == 0
            and int(cleanup_rows[0].get("session_rows") or 0) == 0
            and int(cleanup_rows[0].get("event_rows") or 0) == 0
        )
        result = {
            "connected": True,
            "parallel_active_attempt_conflicts": 0,
            "active_attempt_unique_index": True,
            "parallel_insert_rejected": duplicate_rejected,
            "controlled_active_rows": active_count,
            "active_event_inserted": active_event_inserted,
            "first_end_state": (first_end or {}).get("status"),
            "repeated_end_replayed": bool(repeated_end and repeated_end.get("idempotent_replay")),
            "end_time_stable": end_time_stable,
            "late_event_rejected": not late_event_inserted,
            "controlled_event_rows": event_count,
            "cleanup_verified": cleanup_verified,
        }
        print(result)
        passed = all(
            (
                duplicate_rejected,
                active_count == 1,
                active_event_inserted,
                bool(first_end and not first_end.get("idempotent_replay") and first_end.get("status") == "Ended"),
                bool(repeated_end and repeated_end.get("idempotent_replay")),
                end_time_stable,
                not late_event_inserted,
                event_count == 1,
                cleanup_verified,
            )
        )
        return 0 if passed else 1
    finally:
        try:
            cleanup()
        except Exception:
            pass
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
