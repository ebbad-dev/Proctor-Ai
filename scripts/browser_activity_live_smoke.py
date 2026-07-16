from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database.db_connection import DatabaseConnection
from database.student_repository import StudentRepository


def main() -> int:
    db = DatabaseConnection()
    if not db.connect(max_retries=1):
        raise SystemExit("SQL Server connection failed")

    repo = StudentRepository(db)
    session_id = f"phase1_browser_smoke_{uuid4().hex}"
    browser_ingest_id = uuid4().hex
    event_ingest_id = uuid4().hex
    try:
        event_schema = db.query(
            """
            SELECT CHARACTER_MAXIMUM_LENGTH AS max_length
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'Events' AND COLUMN_NAME = 'session_id'
            """
        )
        if not event_schema or int(event_schema[0].get("max_length") or 0) < 128:
            raise RuntimeError("Events.session_id was not migrated to NVARCHAR(128)")
        repo.insert_browser_activity(
            session_id,
            "tab_switch",
            datetime.now(UTC),
            url="https://example.invalid/phase1-smoke",
            title="Phase 1 browser persistence smoke",
            category="Verification",
            risk_level="medium",
            risk_points=5,
            source="phase1_smoke",
            ingest_id=browser_ingest_id,
            tenant_id="tenant_default",
        )
        browser_duplicate_rejected = False
        try:
            repo.insert_browser_activity(
                session_id,
                "tab_switch",
                datetime.now(UTC),
                source="phase1_smoke",
                ingest_id=browser_ingest_id,
                tenant_id="tenant_default",
            )
        except Exception:
            browser_duplicate_rejected = True
        rows = repo.get_browser_activity(session_id)
        if len(rows) != 1 or rows[0].get("source") != "phase1_smoke" or not browser_duplicate_rejected:
            raise RuntimeError("Browser activity did not round-trip through SQL Server")

        repo.insert_event(
            session_id,
            "student_phase1_smoke",
            "Phase 1 Smoke",
            datetime.now(UTC),
            0,
            "Temporary idempotency smoke row.",
            tenant_id="tenant_default",
            ingest_id=event_ingest_id,
        )
        event_duplicate_rejected = False
        try:
            repo.insert_event(
                session_id,
                "student_phase1_smoke",
                "Phase 1 Smoke",
                datetime.now(UTC),
                0,
                "Temporary duplicate smoke row.",
                tenant_id="tenant_default",
                ingest_id=event_ingest_id,
            )
        except Exception:
            event_duplicate_rejected = True
        event_rows = db.query("SELECT ingest_id FROM Events WHERE session_id = ?", (session_id,))
        if len(event_rows) != 1 or not event_duplicate_rejected:
            raise RuntimeError("Event ingestion ID uniqueness was not enforced")

        print({
            "connected": True,
            "schemas": ["BrowserActivity", "Events"],
            "round_trip": True,
            "browser_duplicate_rejected": browser_duplicate_rejected,
            "event_duplicate_rejected": event_duplicate_rejected,
        })
        return 0
    finally:
        db.execute("DELETE FROM BrowserActivity WHERE session_id = ?", (session_id,))
        db.execute("DELETE FROM Events WHERE session_id = ?", (session_id,))
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
