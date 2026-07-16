from __future__ import annotations

import json
import os
import unittest
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

os.environ["AUTH_SECRET"] = os.environ.get("AUTH_SECRET") or (
    "test-auth-secret-that-is-at-least-thirty-two-characters"
)

from core.security import hash_password, hash_reset_token, verify_password
from services.identity_service import (
    IdentityService,
    IdentityServiceError,
    IdentitySettings,
)


class FakeRepository:
    def __init__(self) -> None:
        self.users_by_email: dict[str, dict] = {}
        self.users_by_id: dict[str, dict] = {}
        self.reset_tokens: dict[str, dict] = {}
        self.used_token_ids: list[str] = []

    def add_user(
        self,
        email: str,
        password: str = "StrongPass1",
        *,
        active: bool = True,
    ) -> dict:
        return self.create_user(
            email,
            "Test User",
            "student",
            hash_password(password),
            active=active,
        )

    def get_user_by_email(self, email: str) -> dict | None:
        return self.users_by_email.get(email)

    def get_user(self, user_id: str) -> dict | None:
        return self.users_by_id.get(user_id)

    def create_user(
        self,
        email: str,
        full_name: str,
        role: str,
        password_hash: str,
        *,
        active: bool = True,
    ) -> dict:
        user = {
            "user_id": f"user_{len(self.users_by_id) + 1}",
            "email": email,
            "full_name": full_name,
            "role": role,
            "tenant_id": "tenant_default",
            "tenant_name": "Default Institution",
            "is_active": active,
            "password_hash": password_hash,
        }
        self.users_by_email[email] = user
        self.users_by_id[user["user_id"]] = user
        return user

    def create_reset_token(self, user_id: str, token_hash: str, expires_at: datetime) -> str:
        token_id = f"reset_{len(self.reset_tokens) + 1}"
        self.reset_tokens[token_hash] = {
            "token_id": token_id,
            "user_id": user_id,
            "expires_at": expires_at,
            "used_at": None,
        }
        return token_id

    def get_reset_token(self, token_hash: str) -> dict | None:
        return self.reset_tokens.get(token_hash)

    def update_password(self, user_id: str, password_hash: str) -> None:
        self.users_by_id[user_id]["password_hash"] = password_hash

    def mark_reset_token_used(self, token_id: str) -> None:
        self.used_token_ids.append(token_id)
        for row in self.reset_tokens.values():
            if row["token_id"] == token_id:
                row["used_at"] = datetime.now(timezone.utc)


class JsonResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class IdentityServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = FakeRepository()
        self.sent_reset: list[tuple[str, str]] = []
        self.service = IdentityService(
            repository_provider=lambda: self.repo,
            settings=IdentitySettings(frontend_url="https://frontend.test"),
            email_is_configured=lambda: True,
            send_reset_email=lambda email, url: self.sent_reset.append((email, url)),
        )

    def test_register_and_login_preserve_the_public_contract(self) -> None:
        registered = self.service.register(
            "  Student@Example.Test ",
            "  Student Name  ",
            "StrongPass1",
        )

        self.assertEqual(registered["token_type"], "bearer")
        self.assertTrue(registered["access_token"])
        self.assertEqual(registered["user"]["email"], "student@example.test")
        self.assertEqual(registered["user"]["full_name"], "Student Name")
        self.assertNotIn("password_hash", registered["user"])

        logged_in = self.service.login("STUDENT@example.test", "StrongPass1")
        self.assertEqual(logged_in["user"], registered["user"])

    def test_login_errors_do_not_disclose_password_state(self) -> None:
        self.repo.add_user("student@example.test", active=False)

        with self.assertRaises(IdentityServiceError) as invalid:
            self.service.login("missing@example.test", "WrongPass1")
        self.assertEqual(invalid.exception.status_code, 401)
        self.assertEqual(invalid.exception.error, "invalid_credentials")

        with self.assertRaises(IdentityServiceError) as disabled:
            self.service.login("student@example.test", "StrongPass1")
        self.assertEqual(disabled.exception.status_code, 403)
        self.assertEqual(disabled.exception.error, "account_disabled")

    def test_password_reset_is_delivered_hashed_and_single_use(self) -> None:
        user = self.repo.add_user("student@example.test")

        requested_user = self.service.request_password_reset("STUDENT@example.test")

        self.assertEqual(requested_user["user_id"], user["user_id"])
        self.assertEqual(len(self.sent_reset), 1)
        reset_url = self.sent_reset[0][1]
        token = parse_qs(urlparse(reset_url).query)["token"][0]
        self.assertNotIn(token, self.repo.reset_tokens)

        reset_user = self.service.reset_password(token, "Replacement2")
        self.assertEqual(reset_user["user_id"], user["user_id"])
        self.assertTrue(verify_password("Replacement2", reset_user["password_hash"]))
        self.assertEqual(self.repo.used_token_ids, ["reset_1"])

        with self.assertRaises(IdentityServiceError) as reused:
            self.service.reset_password(token, "AnotherPass3")
        self.assertEqual(reused.exception.error, "reset_token_used")

    def test_expired_reset_token_is_rejected_without_changing_password(self) -> None:
        user = self.repo.add_user("student@example.test")
        original_hash = user["password_hash"]
        token = "expired-token"
        self.repo.reset_tokens[hash_reset_token(token)] = {
            "token_id": "reset_expired",
            "user_id": user["user_id"],
            "expires_at": datetime.now(timezone.utc) - timedelta(minutes=1),
            "used_at": None,
        }

        with self.assertRaises(IdentityServiceError) as expired:
            self.service.reset_password(token, "Replacement2")
        self.assertEqual(expired.exception.error, "reset_token_expired")
        self.assertEqual(user["password_hash"], original_hash)

    def test_oauth_state_is_signed_tamper_evident_and_expires(self) -> None:
        now = [1_000.0]
        service = IdentityService(
            repository_provider=lambda: self.repo,
            settings=IdentitySettings(frontend_url="https://frontend.test"),
            clock=lambda: now[0],
            random_token=lambda _length: "fixed-nonce",
            auth_secret_provider=lambda: "x" * 32,
        )

        state = service.create_oauth_state()
        self.assertTrue(service.verify_oauth_state(state))
        self.assertFalse(service.verify_oauth_state(f"{state[:-1]}x"))
        now[0] += 601
        self.assertFalse(service.verify_oauth_state(state))

    def test_google_callback_creates_a_local_identity(self) -> None:
        responses = iter(
            [
                {"id_token": "google-id-token"},
                {
                    "aud": "google-client",
                    "email_verified": True,
                    "email": "new@example.test",
                    "name": "New Student",
                },
            ]
        )
        service = IdentityService(
            repository_provider=lambda: self.repo,
            settings=IdentitySettings(
                frontend_url="https://frontend.test",
                google_client_id="google-client",
                google_client_secret="google-secret",
                google_redirect_uri="https://api.test/auth/google/callback",
            ),
            open_url=lambda *_args, **_kwargs: JsonResponse(next(responses)),
            random_token=lambda _length: "fixed-random-token",
            auth_secret_provider=lambda: "x" * 32,
        )
        state = service.create_oauth_state()

        result = service.google_callback(code="authorization-code", state=state)

        self.assertEqual(result["action"], "auth.google_register")
        self.assertEqual(result["session"]["user"]["email"], "new@example.test")
        self.assertNotIn("password_hash", result["session"]["user"])


class IdentityRouterContractTests(unittest.TestCase):
    def test_http_adapter_preserves_auth_payloads_and_errors(self) -> None:
        from fastapi import FastAPI, HTTPException
        from fastapi.testclient import TestClient

        from infrastructure.api.routers.identity import create_identity_router

        repo = FakeRepository()
        audits: list[str] = []
        service = IdentityService(
            repository_provider=lambda: repo,
            settings=IdentitySettings(frontend_url="https://frontend.test"),
        )

        def current_user() -> dict:
            return repo.get_user_by_email("student@example.test") or {}

        def api_error(status_code: int, error: str, message: str, details=None) -> None:
            raise HTTPException(
                status_code=status_code,
                detail={"error": error, "message": message, "details": details},
            )

        app = FastAPI()
        app.include_router(
            create_identity_router(
                service,
                current_user=current_user,
                audit=lambda action, **_kwargs: audits.append(action),
                api_error=api_error,
            )
        )

        with TestClient(app) as client:
            registered = client.post(
                "/auth/register",
                json={
                    "email": "student@example.test",
                    "full_name": "Student Name",
                    "password": "StrongPass1",
                },
            )
            self.assertEqual(registered.status_code, 200)
            self.assertNotIn("password_hash", registered.json()["user"])

            invalid = client.post(
                "/auth/login",
                json={"email": "student@example.test", "password": "WrongPass1"},
            )
            self.assertEqual(invalid.status_code, 401)
            self.assertEqual(invalid.json()["detail"]["error"], "invalid_credentials")

            logged_in = client.post(
                "/auth/login",
                json={"email": "student@example.test", "password": "StrongPass1"},
            )
            self.assertEqual(logged_in.status_code, 200)
            self.assertEqual(logged_in.json()["user"]["role"], "student")
            self.assertEqual(client.get("/auth/me").status_code, 200)

        self.assertEqual(audits, ["auth.register", "auth.login"])

    def test_auth_routes_are_registered_once_by_the_identity_router(self) -> None:
        from infrastructure.api.fastapi_app import app

        expected_paths = {
            "/auth/register",
            "/auth/login",
            "/auth/me",
            "/auth/logout",
            "/auth/forgot-password",
            "/auth/reset-password",
            "/auth/google/start",
            "/auth/google/callback",
        }
        routes = [route for route in app.routes if getattr(route, "path", "") in expected_paths]

        self.assertEqual({route.path for route in routes}, expected_paths)
        self.assertEqual(len(routes), len(expected_paths))
        self.assertTrue(
            all(route.endpoint.__module__ == "infrastructure.api.routers.identity" for route in routes)
        )


if __name__ == "__main__":
    unittest.main()
