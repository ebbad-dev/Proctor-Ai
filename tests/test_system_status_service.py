from __future__ import annotations

import os
import unittest

os.environ["AUTH_SECRET"] = os.environ.get("AUTH_SECRET") or "test-auth-secret-that-is-at-least-thirty-two-characters"

from core.version import APP_VERSION
from services.system_status_service import SystemStatusService


class FakeDatabase:
    is_active = True


class SystemStatusServiceTests(unittest.TestCase):
    def build_service(self, *, guard_last_seen: float = 0.0) -> SystemStatusService:
        return SystemStatusService(
            get_database=lambda: FakeDatabase(),
            get_dashboard_metrics=lambda tenant_id: {"tenant": tenant_id, "sessions": 2},
            get_active_session_id=lambda: "session_1",
            get_tenant_id=lambda user: user["tenant_id"],
            get_guard_last_seen=lambda: guard_last_seen,
            get_event_count=lambda: 3,
            get_browser_event_count=lambda: 4,
            started_at=900.0,
            wall_clock=lambda: 1000.0,
            monotonic_clock=lambda: 100.0,
        )

    def test_health_and_open_status_use_the_central_version(self) -> None:
        service = self.build_service()

        health = service.health()
        status = service.ops_status({"role": "instructor", "tenant_id": "tenant_1"})

        self.assertEqual(health["version"], APP_VERSION)
        self.assertEqual(status["version"], APP_VERSION)
        self.assertEqual(status["uptime_seconds"], 100)

    def test_browser_guard_recency_uses_monotonic_time(self) -> None:
        service = self.build_service(guard_last_seen=90.0)

        status = service.ops_status({"role": "instructor", "tenant_id": "tenant_1"})

        self.assertTrue(status["proctoring"]["browser_guard_active"])

    def test_metrics_are_tenant_scoped_and_include_process_counts(self) -> None:
        service = self.build_service()

        metrics = service.ops_metrics({"role": "admin", "tenant_id": "tenant_2"})

        self.assertEqual(metrics["tenant"], "tenant_2")
        self.assertEqual(metrics["in_memory_events"], 3)
        self.assertEqual(metrics["in_memory_browser_events"], 4)
        self.assertEqual(metrics["active_session_id"], "session_1")


if __name__ == "__main__":
    unittest.main()
