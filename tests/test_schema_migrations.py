from __future__ import annotations

import os
import unittest

os.environ["AUTH_SECRET"] = os.environ.get("AUTH_SECRET") or "test-auth-secret-that-is-at-least-thirty-two-characters"

from database.schema_migrations import Migration, apply_migrations, migration_status


class FakeMigrationDatabase:
    def __init__(self) -> None:
        self.applied: dict[str, dict] = {}

    def execute(self, sql: str, params: tuple = ()) -> int:
        if "INSERT INTO SchemaMigrations" in sql:
            migration_id, description, checksum = params
            self.applied[migration_id] = {
                "migration_id": migration_id,
                "description": description,
                "checksum": checksum,
                "applied_at": "2026-07-16T10:00:00Z",
            }
        return 1

    def query(self, _sql: str, _params: tuple = ()) -> list[dict]:
        return [self.applied[key] for key in sorted(self.applied)]


class SchemaMigrationTests(unittest.TestCase):
    def test_migration_is_applied_once_and_reported_ready(self) -> None:
        db = FakeMigrationDatabase()
        calls: list[str] = []
        migration = Migration("0001", "baseline", "v1", lambda: calls.append("applied"))

        first = apply_migrations(db, [migration])
        second = apply_migrations(db, [migration])
        status = migration_status(db, [migration])

        self.assertEqual(first, ["0001"])
        self.assertEqual(second, [])
        self.assertEqual(calls, ["applied"])
        self.assertTrue(status["ready"])
        self.assertEqual(status["pending"], [])

    def test_checksum_drift_stops_startup(self) -> None:
        db = FakeMigrationDatabase()
        original = Migration("0001", "baseline", "v1", lambda: None)
        apply_migrations(db, [original])
        edited = Migration("0001", "baseline edited", "v1", lambda: None)

        with self.assertRaisesRegex(RuntimeError, "must not be edited"):
            apply_migrations(db, [edited])

    def test_pending_and_unexpected_migrations_are_visible(self) -> None:
        db = FakeMigrationDatabase()
        db.applied["legacy"] = {
            "migration_id": "legacy",
            "description": "legacy",
            "checksum": "legacy",
            "applied_at": "2026-07-16T10:00:00Z",
        }
        expected = Migration("0001", "baseline", "v1", lambda: None)

        status = migration_status(db, [expected])

        self.assertFalse(status["ready"])
        self.assertEqual(status["pending"], ["0001"])
        self.assertEqual(status["unexpected"], ["legacy"])

    def test_concurrent_migration_record_is_treated_as_success(self) -> None:
        class ConcurrentDatabase(FakeMigrationDatabase):
            def execute(self, sql: str, params: tuple = ()) -> int:
                if "INSERT INTO SchemaMigrations" in sql:
                    migration_id, description, checksum = params
                    self.applied[migration_id] = {
                        "migration_id": migration_id,
                        "description": description,
                        "checksum": checksum,
                        "applied_at": "2026-07-16T10:00:00Z",
                    }
                    raise RuntimeError("duplicate key from concurrent process")
                return 1

        db = ConcurrentDatabase()
        migration = Migration("0001", "baseline", "v1", lambda: None)

        newly_applied = apply_migrations(db, [migration])

        self.assertEqual(newly_applied, [])
        self.assertTrue(migration_status(db, [migration])["ready"])


if __name__ == "__main__":
    unittest.main()
