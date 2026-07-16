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
    try:
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
            tenant_id="tenant_default",
        )
        rows = repo.get_browser_activity(session_id)
        if len(rows) != 1 or rows[0].get("source") != "phase1_smoke":
            raise RuntimeError("Browser activity did not round-trip through SQL Server")
        print({"connected": True, "schema": "BrowserActivity", "round_trip": True, "rows": len(rows)})
        return 0
    finally:
        db.execute("DELETE FROM BrowserActivity WHERE session_id = ?", (session_id,))
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
