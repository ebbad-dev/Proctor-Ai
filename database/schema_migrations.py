from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Callable, Iterable


@dataclass(frozen=True)
class Migration:
    migration_id: str
    description: str
    revision: str
    apply: Callable[[], None]

    @property
    def checksum(self) -> str:
        payload = f"{self.migration_id}\0{self.description}\0{self.revision}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def ensure_migration_table(db) -> None:
    db.execute(
        """
        IF OBJECT_ID('SchemaMigrations', 'U') IS NULL
        CREATE TABLE SchemaMigrations (
            migration_id NVARCHAR(128) NOT NULL PRIMARY KEY,
            description NVARCHAR(512) NOT NULL,
            checksum NVARCHAR(64) NOT NULL,
            applied_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
        )
        """
    )


def applied_migrations(db) -> dict[str, dict]:
    rows = db.query(
        """
        SELECT migration_id, description, checksum, applied_at
        FROM SchemaMigrations
        ORDER BY migration_id ASC
        """
    )
    return {str(row["migration_id"]): row for row in rows}


def migration_status(db, migrations: Iterable[Migration]) -> dict:
    ensure_migration_table(db)
    expected = list(migrations)
    applied = applied_migrations(db)
    expected_ids = {migration.migration_id for migration in expected}
    pending = [migration.migration_id for migration in expected if migration.migration_id not in applied]
    drifted = [
        migration.migration_id
        for migration in expected
        if migration.migration_id in applied
        and str(applied[migration.migration_id].get("checksum") or "") != migration.checksum
    ]
    unexpected = sorted(set(applied) - expected_ids)
    return {
        "expected": [migration.migration_id for migration in expected],
        "applied": sorted(applied),
        "pending": pending,
        "drifted": drifted,
        "unexpected": unexpected,
        "ready": not pending and not drifted and not unexpected,
    }


def apply_migrations(db, migrations: Iterable[Migration]) -> list[str]:
    ordered = list(migrations)
    ensure_migration_table(db)
    applied = applied_migrations(db)
    newly_applied: list[str] = []
    for migration in ordered:
        existing = applied.get(migration.migration_id)
        if existing:
            existing_checksum = str(existing.get("checksum") or "")
            if existing_checksum != migration.checksum:
                raise RuntimeError(
                    f"Schema migration checksum mismatch for {migration.migration_id}. "
                    "The applied migration must not be edited in place."
                )
            continue
        migration.apply()
        try:
            db.execute(
                """
                INSERT INTO SchemaMigrations (migration_id, description, checksum, applied_at)
                VALUES (?, ?, ?, SYSUTCDATETIME())
                """,
                (migration.migration_id, migration.description, migration.checksum),
            )
            newly_applied.append(migration.migration_id)
        except Exception:
            concurrent = applied_migrations(db).get(migration.migration_id)
            if not concurrent or str(concurrent.get("checksum") or "") != migration.checksum:
                raise
    return newly_applied
