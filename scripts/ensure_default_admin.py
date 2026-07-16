from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
USER_DEPS = ROOT / "python_user_deps"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if USER_DEPS.exists() and str(USER_DEPS) not in sys.path:
    sys.path.insert(0, str(USER_DEPS))


def load_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def main() -> None:
    load_env()

    email = os.getenv("PROCTORAI_ADMIN_EMAIL") or os.getenv("PROCTORAI_BOOTSTRAP_ADMIN_EMAIL")
    password = os.getenv("PROCTORAI_ADMIN_PASSWORD") or os.getenv("PROCTORAI_BOOTSTRAP_ADMIN_PASSWORD")
    if not email or not password:
        raise SystemExit("Set PROCTORAI_ADMIN_EMAIL/PROCTORAI_ADMIN_PASSWORD or bootstrap admin env vars.")

    from core.security import hash_password
    from database.db_connection import DatabaseConnection
    from database.platform_repository import PlatformRepository

    db = DatabaseConnection()
    if not db.connect(max_retries=1):
        raise SystemExit("SQL Server connection failed.")

    repo = PlatformRepository(db)
    tenant = repo.ensure_default_tenant()
    user = repo.get_user_by_email(email)
    password_hash = hash_password(password)

    if user:
        repo.update_user(
            user["user_id"],
            {
                "tenant_id": user.get("tenant_id") or tenant["tenant_id"],
                "full_name": user.get("full_name") or "ProctorAI Administrator",
                "role": "admin",
                "is_active": True,
            },
        )
        repo.update_password(user["user_id"], password_hash)
        result = repo.get_user(user["user_id"]) or {}
        action = "updated"
    else:
        result = repo.create_user(
            email=email,
            full_name="ProctorAI Administrator",
            role="admin",
            password_hash=password_hash,
            tenant_id=tenant["tenant_id"],
        )
        action = "created"

    print(
        {
            "admin": action,
            "email": result.get("email"),
            "role": result.get("role"),
            "is_active": bool(result.get("is_active", True)),
            "tenant_id": result.get("tenant_id") or tenant["tenant_id"],
        }
    )


if __name__ == "__main__":
    main()
