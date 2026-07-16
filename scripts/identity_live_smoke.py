from __future__ import annotations

import json
import os
import secrets
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if len(os.environ.get("AUTH_SECRET", "")) < 32:
    os.environ["AUTH_SECRET"] = secrets.token_urlsafe(48)

from fastapi.testclient import TestClient

from core.security import verify_password
from database.db_connection import DatabaseConnection
from database.platform_repository import PlatformRepository
from infrastructure.api import fastapi_app as api


def _expect(response, status_code: int, label: str) -> dict:
    if response.status_code != status_code:
        raise RuntimeError(
            f"{label}: expected HTTP {status_code}, got {response.status_code}: "
            f"{response.text[:300]}"
        )
    return response.json() if response.content else {}


def main() -> int:
    marker = uuid.uuid4().hex
    email = f"identity-{marker}@example.invalid"
    password = f"Identity-{secrets.token_urlsafe(18)}-Aa1"
    user_id = ""
    db = DatabaseConnection()
    if not db.connect(max_retries=1):
        raise SystemExit("SQL Server connection failed")
    repo = PlatformRepository(db)

    try:
        with TestClient(api.app) as client:
            registered = _expect(
                client.post(
                    "/auth/register",
                    json={
                        "email": email,
                        "full_name": "Identity Smoke Student",
                        "password": password,
                    },
                ),
                200,
                "register",
            )
            user_id = registered["user"]["user_id"]
            if "password_hash" in registered["user"]:
                raise RuntimeError("register response exposed a password hash")

            persisted = repo.get_user(user_id)
            if not persisted or not verify_password(password, persisted.get("password_hash", "")):
                raise RuntimeError("registered credential was not persisted as a verifiable hash")

            invalid = _expect(
                client.post(
                    "/auth/login",
                    json={"email": email, "password": f"wrong-{password}"},
                ),
                401,
                "invalid login",
            )
            error = invalid.get("error") or (invalid.get("detail") or {}).get("error")
            if error != "invalid_credentials":
                raise RuntimeError("invalid login did not use the stable error contract")

            logged_in = _expect(
                client.post("/auth/login", json={"email": email, "password": password}),
                200,
                "login",
            )
            token = logged_in["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            current = _expect(client.get("/auth/me", headers=headers), 200, "current user")
            if current["user_id"] != user_id or current["email"] != email:
                raise RuntimeError("current-user response does not match the authenticated identity")
            _expect(client.post("/auth/logout", headers=headers), 200, "logout")

        print(
            json.dumps(
                {
                    "status": "passed",
                    "checks": [
                        "registration",
                        "password_hash",
                        "invalid_login",
                        "login",
                        "current_user",
                        "logout",
                    ],
                    "credentials_retained": False,
                },
                indent=2,
            )
        )
        return 0
    finally:
        try:
            persisted = repo.get_user_by_email(email)
            cleanup_user_id = user_id or str((persisted or {}).get("user_id") or "")
            if cleanup_user_id:
                db.execute("DELETE FROM AuditLogs WHERE actor_user_id = ?", (cleanup_user_id,))
                db.execute("DELETE FROM PasswordResetTokens WHERE user_id = ?", (cleanup_user_id,))
                db.execute("DELETE FROM Users WHERE user_id = ?", (cleanup_user_id,))
        finally:
            db.close()


if __name__ == "__main__":
    raise SystemExit(main())
