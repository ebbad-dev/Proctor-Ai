from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from config.settings import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    AUTH_SECRET,
    BROWSER_GUARD_TOKEN_EXPIRE_MINUTES,
    MEDIA_TOKEN_EXPIRE_MINUTES,
    PASSWORD_RESET_EXPIRE_MINUTES,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def require_auth_secret() -> str:
    if not AUTH_SECRET or len(AUTH_SECRET) < 32:
        raise RuntimeError("AUTH_SECRET must be set to at least 32 characters")
    return AUTH_SECRET


def validate_password(password: str) -> list[str]:
    errors: list[str] = []
    if len(password or "") < 8:
        errors.append("Password must be at least 8 characters.")
    if not re.search(r"[A-Z]", password or ""):
        errors.append("Password must include an uppercase letter.")
    if not re.search(r"[a-z]", password or ""):
        errors.append("Password must include a lowercase letter.")
    if not re.search(r"\d", password or ""):
        errors.append("Password must include a number.")
    return errors


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    rounds = 240_000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds)
    return f"pbkdf2_sha256${rounds}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, rounds, salt_b64, digest_b64 = stored.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        salt = _unb64(salt_b64)
        expected = _unb64(digest_b64)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(rounds))
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def create_access_token(user: dict[str, Any]) -> str:
    secret = require_auth_secret().encode("utf-8")
    header = {"alg": "HS256", "typ": "JWT"}
    exp = utc_now() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": user["user_id"],
        "email": user["email"],
        "role": user["role"],
        "name": user.get("full_name", ""),
        "exp": int(exp.timestamp()),
        "iat": int(utc_now().timestamp()),
    }
    signing_input = f"{_b64(json.dumps(header, separators=(',', ':')).encode())}.{_b64(json.dumps(payload, separators=(',', ':')).encode())}"
    signature = hmac.new(secret, signing_input.encode("ascii"), hashlib.sha256).digest()
    return f"{signing_input}.{_b64(signature)}"


def decode_access_token(token: str) -> dict[str, Any]:
    secret = require_auth_secret().encode("utf-8")
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Malformed token")
    signing_input = f"{parts[0]}.{parts[1]}"
    expected = _b64(hmac.new(secret, signing_input.encode("ascii"), hashlib.sha256).digest())
    if not hmac.compare_digest(parts[2], expected):
        raise ValueError("Invalid token signature")
    payload = json.loads(_unb64(parts[1]).decode("utf-8"))
    if int(payload.get("exp", 0)) < int(utc_now().timestamp()):
        raise ValueError("Token expired")
    return payload


def create_browser_guard_token(user: dict[str, Any], session_id: str) -> str:
    """Create a short-lived token that can only ingest browser signals for one session."""
    secret = require_auth_secret().encode("utf-8")
    now = utc_now()
    payload = {
        "sub": user["user_id"],
        "tenant_id": user.get("tenant_id") or "tenant_default",
        "session_id": session_id,
        "purpose": "browser_guard",
        "exp": int((now + timedelta(minutes=BROWSER_GUARD_TOKEN_EXPIRE_MINUTES)).timestamp()),
        "iat": int(now.timestamp()),
    }
    body = _b64(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = _b64(hmac.new(secret, f"browser_guard.{body}".encode("ascii"), hashlib.sha256).digest())
    return f"{body}.{signature}"


def decode_browser_guard_token(token: str) -> dict[str, Any]:
    secret = require_auth_secret().encode("utf-8")
    parts = token.split(".")
    if len(parts) != 2:
        raise ValueError("Malformed browser guard token")
    body, signature = parts
    expected = _b64(hmac.new(secret, f"browser_guard.{body}".encode("ascii"), hashlib.sha256).digest())
    if not hmac.compare_digest(signature, expected):
        raise ValueError("Invalid browser guard token signature")
    payload = json.loads(_unb64(body).decode("utf-8"))
    if payload.get("purpose") != "browser_guard":
        raise ValueError("Invalid browser guard token purpose")
    if int(payload.get("exp", 0)) < int(utc_now().timestamp()):
        raise ValueError("Browser guard token expired")
    if not payload.get("sub") or not payload.get("session_id"):
        raise ValueError("Browser guard token is missing required claims")
    return payload


def create_media_token(user: dict[str, Any], session_id: str) -> str:
    """Create a short-lived bearer suitable for an MJPEG image query parameter."""
    secret = require_auth_secret().encode("utf-8")
    now = utc_now()
    payload = {
        "sub": user["user_id"],
        "tenant_id": user.get("tenant_id") or "tenant_default",
        "session_id": session_id,
        "purpose": "video_stream",
        "exp": int((now + timedelta(minutes=MEDIA_TOKEN_EXPIRE_MINUTES)).timestamp()),
        "iat": int(now.timestamp()),
    }
    body = _b64(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = _b64(hmac.new(secret, f"video_stream.{body}".encode("ascii"), hashlib.sha256).digest())
    return f"{body}.{signature}"


def decode_media_token(token: str) -> dict[str, Any]:
    secret = require_auth_secret().encode("utf-8")
    parts = token.split(".")
    if len(parts) != 2:
        raise ValueError("Malformed media token")
    body, signature = parts
    expected = _b64(hmac.new(secret, f"video_stream.{body}".encode("ascii"), hashlib.sha256).digest())
    if not hmac.compare_digest(signature, expected):
        raise ValueError("Invalid media token signature")
    payload = json.loads(_unb64(body).decode("utf-8"))
    if payload.get("purpose") != "video_stream":
        raise ValueError("Invalid media token purpose")
    if int(payload.get("exp", 0)) < int(utc_now().timestamp()):
        raise ValueError("Media token expired")
    if not payload.get("sub") or not payload.get("session_id"):
        raise ValueError("Media token is missing required claims")
    return payload


def create_reset_token() -> tuple[str, str, datetime]:
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    expires_at = utc_now() + timedelta(minutes=PASSWORD_RESET_EXPIRE_MINUTES)
    return token, token_hash, expires_at


def hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
