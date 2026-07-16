from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable
from urllib import request as urlrequest
from urllib.parse import quote, urlencode

from core.email_service import (
    EmailConfigurationError,
    send_password_reset_email,
    smtp_configured,
)
from core.security import (
    create_access_token,
    create_reset_token,
    hash_password,
    hash_reset_token,
    require_auth_secret,
    validate_password,
    verify_password,
)


class IdentityServiceError(Exception):
    def __init__(
        self,
        status_code: int,
        error: str,
        message: str,
        details: Any = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error = error
        self.message = message
        self.details = details


class OAuthFlowError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class IdentitySettings:
    frontend_url: str
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = ""


def public_user(user: dict) -> dict:
    return {
        "user_id": str(user.get("user_id", "")),
        "email": str(user.get("email", "")),
        "full_name": str(user.get("full_name", "")),
        "role": str(user.get("role", "")),
        "tenant_id": str(user.get("tenant_id") or "tenant_default"),
        "tenant_name": str(user.get("tenant_name") or "Default Institution"),
        "is_active": bool(user.get("is_active", True)),
        "created_at": user.get("created_at"),
        "updated_at": user.get("updated_at"),
    }


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64url(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


@dataclass
class IdentityService:
    repository_provider: Callable[[], Any]
    settings: IdentitySettings
    email_is_configured: Callable[[], bool] = smtp_configured
    send_reset_email: Callable[[str, str], None] = send_password_reset_email
    open_url: Callable[..., Any] = urlrequest.urlopen
    clock: Callable[[], float] = time.time
    random_token: Callable[[int], str] = secrets.token_urlsafe
    auth_secret_provider: Callable[[], str] = require_auth_secret
    _oauth_state_lifetime_seconds: int = field(default=600, repr=False)

    @staticmethod
    def public_user(user: dict) -> dict:
        return public_user(user)

    def register(self, email: str, full_name: str, password: str) -> dict:
        normalized_email = (email or "").strip().lower()
        normalized_name = (full_name or "").strip()
        if "@" not in normalized_email or "." not in normalized_email.rsplit("@", 1)[-1]:
            raise IdentityServiceError(422, "validation_error", "Enter a valid email address.")
        if len(normalized_name) < 2:
            raise IdentityServiceError(422, "validation_error", "Enter your full name.")
        errors = validate_password(password)
        if errors:
            raise IdentityServiceError(
                422,
                "validation_error",
                "Password does not meet requirements.",
                errors,
            )

        repo = self.repository_provider()
        if repo.get_user_by_email(normalized_email):
            raise IdentityServiceError(
                409,
                "email_exists",
                "An account with this email already exists.",
            )
        user = repo.create_user(
            normalized_email,
            normalized_name,
            "student",
            hash_password(password),
        )
        return self._auth_session(user)

    def login(self, email: str, password: str) -> dict:
        repo = self.repository_provider()
        user = repo.get_user_by_email((email or "").strip().lower())
        if not user or not verify_password(password, user.get("password_hash", "")):
            raise IdentityServiceError(
                401,
                "invalid_credentials",
                "Email or password is incorrect.",
            )
        if not bool(user.get("is_active", True)):
            raise IdentityServiceError(403, "account_disabled", "This account is disabled.")
        return self._auth_session(user)

    def request_password_reset(self, email: str) -> dict:
        if not self.email_is_configured():
            raise IdentityServiceError(
                503,
                "email_not_configured",
                "Password reset email is not configured.",
            )
        repo = self.repository_provider()
        user = repo.get_user_by_email((email or "").strip().lower())
        if not user:
            raise IdentityServiceError(
                404,
                "email_not_found",
                "No account exists for that email address.",
            )

        token, token_hash, expires_at = create_reset_token()
        repo.create_reset_token(user["user_id"], token_hash, expires_at)
        reset_url = f"{self.settings.frontend_url}/reset-password?token={token}"
        try:
            self.send_reset_email(user["email"], reset_url)
        except EmailConfigurationError as exc:
            raise IdentityServiceError(
                503,
                "email_not_configured",
                str(exc) or "Password reset email is not configured.",
            ) from exc
        except Exception as exc:
            raise IdentityServiceError(
                502,
                "email_delivery_failed",
                "Could not send the reset email.",
            ) from exc
        return user

    def reset_password(self, token: str, password: str) -> dict:
        errors = validate_password(password)
        if errors:
            raise IdentityServiceError(
                422,
                "validation_error",
                "Password does not meet requirements.",
                errors,
            )
        repo = self.repository_provider()
        row = repo.get_reset_token(hash_reset_token(token))
        if not row:
            raise IdentityServiceError(400, "invalid_reset_token", "The reset link is invalid.")
        if row.get("used_at"):
            raise IdentityServiceError(
                400,
                "reset_token_used",
                "The reset link has already been used.",
            )
        try:
            expires_at = _parse_datetime(row.get("expires_at"))
        except Exception as exc:
            raise IdentityServiceError(
                400,
                "invalid_reset_token",
                "The reset link is invalid.",
            ) from exc
        if expires_at < datetime.now(expires_at.tzinfo or timezone.utc):
            raise IdentityServiceError(
                400,
                "reset_token_expired",
                "The reset link has expired.",
            )

        repo.update_password(row["user_id"], hash_password(password))
        repo.mark_reset_token_used(row["token_id"])
        return repo.get_user(row["user_id"])

    def google_start_url(self) -> str:
        if not self.settings.google_client_id:
            raise OAuthFlowError("google_not_configured", "Google sign-in is not configured.")
        params = urlencode(
            {
                "client_id": self.settings.google_client_id,
                "redirect_uri": self.settings.google_redirect_uri,
                "response_type": "code",
                "scope": "openid email profile",
                "state": self.create_oauth_state(),
                "access_type": "online",
                "prompt": "select_account",
            }
        )
        return f"https://accounts.google.com/o/oauth2/v2/auth?{params}"

    def google_callback(self, code: str = "", state: str = "", error: str = "") -> dict:
        if error:
            raise OAuthFlowError("google_denied", "Google sign-in was cancelled.")
        if not self.settings.google_client_id or not self.settings.google_client_secret:
            raise OAuthFlowError("google_not_configured", "Google sign-in is not configured.")
        if not code or not state or not self.verify_oauth_state(state):
            raise OAuthFlowError(
                "invalid_oauth_state",
                "Google sign-in session expired. Try again.",
            )

        try:
            token_body = urlencode(
                {
                    "code": code,
                    "client_id": self.settings.google_client_id,
                    "client_secret": self.settings.google_client_secret,
                    "redirect_uri": self.settings.google_redirect_uri,
                    "grant_type": "authorization_code",
                }
            ).encode("utf-8")
            token_request = urlrequest.Request(
                "https://oauth2.googleapis.com/token",
                data=token_body,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                method="POST",
            )
            token_payload = self._read_json(token_request)
            id_token = token_payload.get("id_token")
            if not id_token:
                raise OAuthFlowError(
                    "google_token_missing",
                    "Google did not return an identity token.",
                )
            claims = self._read_json(
                f"https://oauth2.googleapis.com/tokeninfo?id_token={quote(str(id_token))}"
            )
        except OAuthFlowError:
            raise
        except Exception as exc:
            raise OAuthFlowError(
                "google_exchange_failed",
                "Could not verify your Google account.",
            ) from exc

        if claims.get("aud") != self.settings.google_client_id or claims.get(
            "email_verified"
        ) not in {True, "true", "True", "1"}:
            raise OAuthFlowError(
                "google_identity_invalid",
                "Google account verification failed.",
            )

        email = str(claims.get("email") or "").strip().lower()
        full_name = str(claims.get("name") or email.split("@", 1)[0] or "Google User").strip()
        if not email:
            raise OAuthFlowError(
                "google_email_missing",
                "Google did not provide an email address.",
            )

        repo = self.repository_provider()
        user = repo.get_user_by_email(email)
        if user and not bool(user.get("is_active", True)):
            raise OAuthFlowError("account_disabled", "This account is disabled.")
        if user:
            action = "auth.google_login"
        else:
            user = repo.create_user(
                email,
                full_name,
                "student",
                hash_password(self.random_token(32)),
            )
            action = "auth.google_register"
        return {"action": action, "user": user, "session": self._auth_session(user)}

    def create_oauth_state(self) -> str:
        payload = {
            "nonce": self.random_token(18),
            "exp": int(self.clock()) + self._oauth_state_lifetime_seconds,
            "provider": "google",
        }
        body = _b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
        signature = _b64url(
            hmac.new(
                self.auth_secret_provider().encode("utf-8"),
                body.encode("ascii"),
                hashlib.sha256,
            ).digest()
        )
        return f"{body}.{signature}"

    def verify_oauth_state(self, state: str) -> bool:
        try:
            body, signature = state.split(".", 1)
            expected = _b64url(
                hmac.new(
                    self.auth_secret_provider().encode("utf-8"),
                    body.encode("ascii"),
                    hashlib.sha256,
                ).digest()
            )
            if not hmac.compare_digest(signature, expected):
                return False
            payload = json.loads(_unb64url(body).decode("utf-8"))
            return payload.get("provider") == "google" and int(
                payload.get("exp", 0)
            ) >= int(self.clock())
        except Exception:
            return False

    def oauth_error_url(self, code: str, message: str) -> str:
        return (
            f"{self.settings.frontend_url}/login?oauth_error={quote(message)}"
            f"&oauth_code={quote(code)}"
        )

    def oauth_success_url(self, session: dict) -> str:
        payload = _b64url(
            json.dumps(session, default=str, separators=(",", ":")).encode("utf-8")
        )
        return f"{self.settings.frontend_url}/oauth-callback#session={payload}"

    def _auth_session(self, user: dict) -> dict:
        return {
            "access_token": create_access_token(user),
            "token_type": "bearer",
            "user": public_user(user),
        }

    def _read_json(self, target: Any) -> dict:
        with self.open_url(target, timeout=12) as response:
            return json.loads(response.read().decode("utf-8"))
