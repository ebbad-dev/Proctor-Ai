from __future__ import annotations

import json
import os
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.security import hash_password
from database.db_connection import DatabaseConnection
from database.platform_repository import PlatformRepository


ARTIFACTS = ROOT / "e2e_artifacts"
SEED_PATH = ARTIFACTS / "seed.json"
STUDENT_EMAIL = os.getenv("PROCTORAI_E2E_STUDENT_EMAIL", "student.e2e@proctorai.local")
ADMIN_EMAIL = os.getenv("PROCTORAI_E2E_ADMIN_EMAIL", "admin.e2e@proctorai.local")


def _e2e_password(variable: str) -> str:
    """Use an operator-supplied password or create an ephemeral high-entropy one."""
    return os.getenv(variable) or secrets.token_urlsafe(32)


def ensure_user(repo: PlatformRepository, email: str, full_name: str, role: str, password: str) -> dict:
    user = repo.get_user_by_email(email)
    if user:
        repo.update_password(user["user_id"], hash_password(password))
        return repo.get_user(user["user_id"]) or user
    return repo.create_user(email, full_name, role, hash_password(password))


def main() -> int:
    student_password = _e2e_password("PROCTORAI_E2E_STUDENT_PASSWORD")
    admin_password = _e2e_password("PROCTORAI_E2E_ADMIN_PASSWORD")
    db = DatabaseConnection()
    if not db.connect(max_retries=1):
        raise RuntimeError("Could not connect to SQL Server for E2E seed data.")
    repo = PlatformRepository(db)
    admin = ensure_user(repo, ADMIN_EMAIL, "E2E Admin", "admin", admin_password)
    student = ensure_user(repo, STUDENT_EMAIL, "E2E Student", "student", student_password)
    exam = repo.create_exam(
        {
            "title": "ProctorAI End-to-End Verification Exam",
            "description": "Automated run from login through monitoring, risk, review, and report.",
            "duration_minutes": 30,
            "status": "published",
            "rules": {
                "policy": "Stay in fullscreen, keep camera and microphone enabled, and do not leave the exam tab.",
                "browser_guard_required": True,
                "phone_detection": True,
            },
        },
        admin["user_id"],
    )
    repo.assign_exam(exam["exam_id"], student["user_id"], admin["user_id"])
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    payload = {
        "student": {
            "email": STUDENT_EMAIL,
            "password": student_password,
            "full_name": student["full_name"],
            "user_id": student["user_id"],
        },
        "admin": {
            "email": ADMIN_EMAIL,
            "password": admin_password,
            "full_name": admin["full_name"],
            "user_id": admin["user_id"],
        },
        "exam": {
            "exam_id": exam["exam_id"],
            "title": exam["title"],
        },
    }
    SEED_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "seed_path": str(SEED_PATH),
                "student_email": STUDENT_EMAIL,
                "admin_email": ADMIN_EMAIL,
                "exam_id": exam["exam_id"],
                "credentials_written": True,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
