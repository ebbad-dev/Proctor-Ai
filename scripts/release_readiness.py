from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _check(results: dict, name: str, passed: bool, detail: str) -> None:
    results[name] = {"passed": bool(passed), "detail": detail}


def _static_checks(results: dict) -> None:
    required = (
        "requirements.lock.txt",
        "frontend/package-lock.json",
        "database/schema_migrations.py",
        "infrastructure/api/routers/system.py",
        "services/system_status_service.py",
        ".github/workflows/ci.yml",
    )
    missing = [path for path in required if not (ROOT / path).exists()]
    _check(results, "required_release_files", not missing, "present" if not missing else f"missing: {', '.join(missing)}")
    _check(
        results,
        "python_version",
        sys.version_info >= (3, 12),
        f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
    )
    lock_text = (ROOT / "requirements.lock.txt").read_text(encoding="utf-8")
    _check(results, "hashed_python_lock", "--hash=sha256:" in lock_text, "hash-pinned" if "--hash=sha256:" in lock_text else "hashes missing")

    from database.db_connection import DatabaseConnection

    migrations = list(DatabaseConnection().registered_migrations())
    migration_ids = [migration.migration_id for migration in migrations]
    valid_registry = bool(migrations) and len(migration_ids) == len(set(migration_ids)) and all(
        len(migration.checksum) == 64 for migration in migrations
    )
    _check(
        results,
        "migration_registry",
        valid_registry,
        f"{len(migrations)} registered migration(s)",
    )


def _production_checks(results: dict) -> None:
    from config import settings

    _check(results, "production_environment", settings.APP_ENV.lower() in {"production", "prod"}, settings.APP_ENV)
    _check(results, "auth_secret", len(settings.AUTH_SECRET) >= 32, "configured" if len(settings.AUTH_SECRET) >= 32 else "missing or too short")
    _check(
        results,
        "device_secret",
        len(settings.PROCTOR_DEVICE_SECRET) >= 32,
        "configured" if len(settings.PROCTOR_DEVICE_SECRET) >= 32 else "missing or too short",
    )
    _check(results, "cors_wildcard", "*" not in settings.CORS_ORIGINS, "restricted" if "*" not in settings.CORS_ORIGINS else "wildcard is forbidden")
    _check(
        results,
        "bootstrap_password_disabled",
        not settings.PROCTORAI_BOOTSTRAP_ADMIN_PASSWORD,
        "not retained" if not settings.PROCTORAI_BOOTSTRAP_ADMIN_PASSWORD else "bootstrap password must be removed",
    )


def _database_checks(results: dict) -> None:
    from database.db_connection import DatabaseConnection
    from database.schema_migrations import migration_status

    db = DatabaseConnection()
    connected = db.connect(max_retries=1)
    _check(results, "database_connection", connected, "connected" if connected else "connection failed")
    if not connected:
        return
    try:
        status = migration_status(db, db.registered_migrations())
        _check(
            results,
            "database_migrations",
            bool(status.get("ready")),
            json.dumps({key: status[key] for key in ("applied", "pending", "drifted", "unexpected")}),
        )
        conflicts = db.query(
            """
            SELECT user_id, COUNT(*) AS active_count
            FROM ExamAttempts
            WHERE status = 'in_progress'
            GROUP BY user_id
            HAVING COUNT(*) > 1
            """
        )
        _check(results, "active_attempt_integrity", not conflicts, f"{len(conflicts)} conflict(s)")
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify ProctorAI release prerequisites without exposing secrets.")
    parser.add_argument("--production", action="store_true", help="Validate production-only security settings.")
    parser.add_argument("--database", action="store_true", help="Connect to SQL Server and verify migrations/invariants.")
    args = parser.parse_args()

    results: dict[str, dict] = {}
    _static_checks(results)
    if args.production:
        _production_checks(results)
    if args.database:
        _database_checks(results)
    ready = all(item["passed"] for item in results.values())
    print(json.dumps({"ready": ready, "checks": results}, indent=2, sort_keys=True))
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
