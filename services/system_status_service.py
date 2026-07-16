from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from core.version import APP_VERSION


@dataclass
class SystemStatusService:
    get_database: Callable[[], object | None]
    get_dashboard_metrics: Callable[[str], dict]
    get_active_session_id: Callable[[], str]
    get_tenant_id: Callable[[dict], str]
    get_guard_last_seen: Callable[[], float]
    get_event_count: Callable[[], int]
    get_browser_event_count: Callable[[], int]
    started_at: float
    wall_clock: Callable[[], float] = field(default=time.time)
    monotonic_clock: Callable[[], float] = field(default=time.monotonic)

    def health(self) -> dict:
        return {"status": "healthy", "service": "proctorai-backend", "version": APP_VERSION}

    def ops_status(self, user: dict) -> dict:
        from config import settings

        db = self.get_database()
        migration_state = {"ready": False, "pending": [], "drifted": [], "status": "unavailable"}
        if db and getattr(db, "is_active", False) and hasattr(db, "registered_migrations"):
            try:
                from database.schema_migrations import migration_status

                migration_state = {
                    **migration_status(db, db.registered_migrations()),
                    "status": "ready",
                }
            except Exception as exc:
                migration_state = {
                    "ready": False,
                    "pending": [],
                    "drifted": [],
                    "status": "error",
                    "error": exc.__class__.__name__,
                }
        guard_last_seen = self.get_guard_last_seen()
        return {
            "status": "ok",
            "environment": settings.APP_ENV,
            "version": APP_VERSION,
            "uptime_seconds": int(self.wall_clock() - self.started_at),
            "python": sys.version.split()[0],
            "database": {
                "connected": bool(db and getattr(db, "is_active", False)),
                "name": settings.DB_NAME,
                "driver": settings.DB_DRIVER,
                "migrations": migration_state,
            },
            "storage": {
                "logs_dir": settings.LOGS_DIR,
                "reports_dir": settings.REPORTS_DIR,
                "screenshots_dir": settings.SCREENSHOTS_DIR,
            },
            "proctoring": {
                "phone_model_available": Path(settings.PHONE_MODEL_PATH).exists(),
                "browser_guard_active": bool(
                    guard_last_seen and (self.monotonic_clock() - guard_last_seen) < 15
                ),
            },
            "auth": {"role": user.get("role"), "tenant_id": self.get_tenant_id(user)},
        }

    def ops_metrics(self, user: dict) -> dict:
        metrics = self.get_dashboard_metrics(self.get_tenant_id(user))
        metrics.update(
            {
                "uptime_seconds": int(self.wall_clock() - self.started_at),
                "in_memory_events": self.get_event_count(),
                "in_memory_browser_events": self.get_browser_event_count(),
                "active_session_id": self.get_active_session_id(),
            }
        )
        return metrics
