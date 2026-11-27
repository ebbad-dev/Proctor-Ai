from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta, timezone

os.environ["AUTH_SECRET"] = os.environ.get("AUTH_SECRET") or (
    "test-auth-secret-that-is-at-least-thirty-two-characters"
)

from database.db_connection import DatabaseConnection, _as_utc
from services.exam_service import format_exam, iso


class FakeCursor:
    description = [("start_time",), ("title",)]

    def execute(self, sql, params) -> None:
        pass

    def fetchall(self):
        return [(datetime(2026, 7, 16, 13, 19, 48), "Midterm")]

    def close(self) -> None:
        pass


class FakeConnection:
    def cursor(self) -> FakeCursor:
        return FakeCursor()


class UtcSerializationTests(unittest.TestCase):
    def test_naive_database_datetimes_are_returned_as_utc(self) -> None:
        db = DatabaseConnection()
        db.connection = FakeConnection()
        row = db.query("SELECT start_time, title FROM Exams")[0]
        self.assertEqual(row["start_time"], datetime(2026, 7, 16, 13, 19, 48, tzinfo=timezone.utc))
        self.assertEqual(row["title"], "Midterm")

    def test_aware_datetimes_are_left_unchanged(self) -> None:
        karachi = timezone(timedelta(hours=5))
        value = datetime(2026, 7, 16, 18, 19, tzinfo=karachi)
        self.assertIs(_as_utc(value), value)

    def test_exam_times_are_serialized_with_a_utc_marker(self) -> None:
        self.assertEqual(iso(datetime(2026, 7, 16, 13, 19)), "2026-07-16T13:19:00Z")
        self.assertEqual(
            iso(datetime(2026, 7, 16, 18, 19, tzinfo=timezone(timedelta(hours=5)))),
            "2026-07-16T13:19:00Z",
        )
        exam = format_exam({"exam_id": "exam_1", "start_time": datetime(2026, 7, 16, 13, 19)})
        self.assertTrue(exam["start_time"].endswith("Z"))


if __name__ == "__main__":
    unittest.main()
