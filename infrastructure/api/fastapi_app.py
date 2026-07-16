# ============================================================
# ProctorAI — infrastructure/api/fastapi_app.py
#
# Phase 12: FastAPI backend foundation.
# Runs alongside Streamlit as a separate process on port 5051.
# Receives browser guard events, provides session/event APIs.
#
# Start: uvicorn infrastructure.api.fastapi_app:app --port 5051
# ============================================================

from __future__ import annotations
import base64
import hashlib
import hmac
import os
import json
import secrets
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional
from urllib.parse import quote, urlencode
from urllib import request as urlrequest
from pathlib import Path

_FASTAPI_IMPORT_ERROR = None

try:
    from fastapi import Depends, FastAPI, Header, HTTPException, Request
    from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
    _FASTAPI_AVAILABLE = True
except Exception as exc:
    _FASTAPI_AVAILABLE = False
    _FASTAPI_IMPORT_ERROR = exc

if _FASTAPI_AVAILABLE:
    from config.settings import APP_ENV, LOG_LEVEL, LOGS_DIR, REQUEST_LOGGING
    from core.observability import configure_logging, log_event, request_id_var

    _app_started_at = time.time()
    _api_logger = configure_logging(LOGS_DIR, LOG_LEVEL)

    app = FastAPI(
        title="ProctorAI Backend API",
        description="Receives browser guard events, provides session and event data.",
        version="1.0.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=__import__("config.settings", fromlist=["CORS_ORIGINS"]).CORS_ORIGINS,
        allow_origin_regex=r"chrome-extension://.*",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_observability_middleware(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            log_event(
                _api_logger,
                "api.request.failed",
                level="exception",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                duration_ms=duration_ms,
                error=exc.__class__.__name__,
            )
            request_id_var.reset(token)
            raise

        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        response.headers["x-request-id"] = request_id
        response.headers["x-content-type-options"] = "nosniff"
        response.headers["x-frame-options"] = "DENY"
        response.headers["referrer-policy"] = "strict-origin-when-cross-origin"
        response.headers["permissions-policy"] = "camera=(self), microphone=(self), fullscreen=(self)"
        response.headers["cache-control"] = "no-store" if request.url.path.startswith("/auth") else response.headers.get("cache-control", "no-cache")
        if REQUEST_LOGGING:
            log_event(
                _api_logger,
                "api.request",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=duration_ms,
                client_host=request.client.host if request.client else "",
            )
        request_id_var.reset(token)
        return response

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_: Request, exc: HTTPException):
        if isinstance(exc.detail, dict) and "error" in exc.detail:
            return JSONResponse(status_code=exc.status_code, content=exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": "http_error", "message": str(exc.detail)},
        )

    # ── Mount static files for evidence screenshots ───────────

    # ── In-memory event store ─────────────────────────────────
    _events:       list[dict] = []
    _browser_events: list[dict] = []
    _guard_last_seen = 0.0
    _session_meta: dict = {}
    _session_store: dict[str, dict] = {}
    _session_reviews: dict[str, dict] = {}

    # ── Models ────────────────────────────────────────────────

    class HealthResponse(BaseModel):
        status: str
        service: str
        version: str

    class BrowserGuardEvent(BaseModel):
        type:     str
        url:      str = ""
        title:    str = ""
        category: str = ""
        risk:     str = "low"
        session_id: Optional[str] = None
        source: str = "browser_guard"
        version: str = ""
        ingest_id: str = ""

    class BrowserGuardTokenRequest(BaseModel):
        session_id: str

    class ProctorEvent(BaseModel):
        event_type:  str
        session_id:  str = ""
        student_id:  str = ""
        risk_points: int = 0
        notes:       str = ""
        confidence: Optional[float] = None
        model_name: str = ""
        detection_class: str = ""
        bounding_box: Optional[dict] = None
        evidence_id: str = ""
        ingest_id: str = ""

    class SessionMeta(BaseModel):
        session_id:   str = ""
        student_name: str = ""
        student_id:   str = ""
        exam_code:    str = ""
        exam_id:      str = ""
        roll_number:  str = ""
        started_at:   str = ""

    class EventItem(BaseModel):
        event_id: Optional[Any] = None
        session_id: str
        student_id: str
        event_type: str
        event_time: str
        risk_points: int
        confidence: Optional[float] = None
        model_name: Optional[str] = None
        detection_class: Optional[str] = None
        bounding_box_json: Optional[str] = None
        evidence_id: Optional[str] = None
        ingest_id: Optional[str] = None
        notes: str

    class RiskContributor(BaseModel):
        event_type: str
        points: int

    class RiskResponse(BaseModel):
        session_id: str
        risk_score: int
        risk_level: str
        contributors: List[RiskContributor]

    class EvidenceItem(BaseModel):
        session_id: Optional[str] = None
        filename: str
        event_type: str
        timestamp: str
        filepath: str
        risk_points: Optional[int] = None
        camera: Optional[str] = None

    class BrowserActivityItem(BaseModel):
        session_id: Optional[str] = None
        type: str
        url: str
        title: str
        category: str
        risk: str
        risk_points: Optional[int] = None
        risk_impact: Optional[int] = None
        source: Optional[str] = None
        ingest_id: Optional[str] = None
        time: str
        timestamp: str

    class SessionSummary(BaseModel):
        session_id: str
        user_id: Optional[str] = None
        exam_id: Optional[str] = None
        student_id: str
        exam_code: str
        start_time: Optional[str]
        end_time: Optional[str]
        status: str
        final_score: Optional[int] = None
        review_mark: Optional[str] = None
        instructor_notes: Optional[str] = None

    class SessionDetail(SessionSummary):
        events: List[EventItem]
        event_count: int

    class ReportMetadata(BaseModel):
        session_id: str
        status: str
        risk_score: int
        risk_level: str
        generated_at: str
        pdf_url: str
        summary: str

    class GenerateReportRequest(BaseModel):
        session_id: str

    class ReviewRequest(BaseModel):
        review_mark: str
        instructor_notes: str

    class ReviewResponse(BaseModel):
        status: str
        session_id: str

    class ErrorResponse(BaseModel):
        detail: str

    class ProctorStartRequest(BaseModel):
        session_id: str
        student_id: str = ""
        exam_code: str = ""

    class ProctorControlResponse(BaseModel):
        status: str
        session_id: Optional[str] = None

    class UserPublic(BaseModel):
        user_id: str
        email: str
        full_name: str
        role: str
        tenant_id: str = "tenant_default"
        tenant_name: str = "Default Institution"
        is_active: bool = True
        created_at: Optional[Any] = None
        updated_at: Optional[Any] = None

    class AuthResponse(BaseModel):
        access_token: str
        token_type: str = "bearer"
        user: UserPublic

    class RegisterRequest(BaseModel):
        email: str
        full_name: str
        password: str

    class LoginRequest(BaseModel):
        email: str
        password: str

    class ForgotPasswordRequest(BaseModel):
        email: str

    class ResetPasswordRequest(BaseModel):
        token: str
        password: str

    class ExamRequest(BaseModel):
        exam_code: str = ""
        title: str
        description: str = ""
        semester: str = ""
        subject: str = ""
        department: str = ""
        total_marks: int = 0
        duration_minutes: int = 60
        start_time: Optional[str] = None
        end_time: Optional[str] = None
        status: str = "draft"
        rules: Any = None

    class QuestionOptionRequest(BaseModel):
        option_id: str = ""
        option_text: str = ""
        is_correct: bool = False
        sort_order: int = 0

    class ExamQuestionRequest(BaseModel):
        question_id: str = ""
        question_text: str
        question_type: str = "mcq"
        marks: int = 1
        sort_order: int = 0
        status: str = "active"
        options: List[QuestionOptionRequest] = []

    class ExamCodeJoinRequest(BaseModel):
        exam_code: str

    class AttemptStartRequest(BaseModel):
        exam_id: str
        roll_number: str
        session_id: str = ""

    class AttemptResponseRequest(BaseModel):
        question_id: str
        selected_option_id: str = ""
        response_text: str = ""

    class AttemptSubmitRequest(BaseModel):
        generate_report: bool = True

    class AssignmentRequest(BaseModel):
        student_email: str

    class AssignmentItem(BaseModel):
        assignment_id: str
        tenant_id: Optional[str] = None
        exam_id: str
        student_user_id: str
        student_email: str = ""
        student_name: str = ""
        student_active: bool = True
        assigned_at: Optional[Any] = None
        status: str = "assigned"

    class SessionEndRequest(BaseModel):
        generate_report: bool = True

    class EvidenceCaptureRequest(BaseModel):
        session_id: str
        evidence_type: str
        label: str = ""
        image_data: str = ""
        filepath: str = ""
        confidence: Optional[float] = None
        model_name: str = ""
        detection_class: str = ""
        bounding_box: Optional[dict] = None

    class SettingsRequest(BaseModel):
        values: dict

    class TenantRequest(BaseModel):
        name: str
        slug: str
        plan_name: str = "enterprise"
        status: str = "active"
        settings: dict = {}

    class AdminUserCreateRequest(BaseModel):
        email: str
        full_name: str
        role: str = "student"
        tenant_id: str = "tenant_default"
        password: str

    class AdminUserUpdateRequest(BaseModel):
        full_name: Optional[str] = None
        role: Optional[str] = None
        tenant_id: Optional[str] = None
        is_active: Optional[bool] = None

    class AdminPasswordRequest(BaseModel):
        password: str

    # Shared API dependencies must be defined before routes reference them.
    _db_connection = None
    _db_retry_after = 0.0
    _bootstrap_checked = False

    def _api_error(status_code: int, error: str, message: str, details: Any = None):
        payload = {"error": error, "message": message}
        if details is not None:
            payload["details"] = details
        raise HTTPException(status_code=status_code, detail=payload)

    def _bootstrap_admin(db) -> None:
        from config.settings import PROCTORAI_BOOTSTRAP_ADMIN_EMAIL, PROCTORAI_BOOTSTRAP_ADMIN_PASSWORD
        if not PROCTORAI_BOOTSTRAP_ADMIN_EMAIL or not PROCTORAI_BOOTSTRAP_ADMIN_PASSWORD:
            return
        from core.security import hash_password, validate_password
        from database.platform_repository import PlatformRepository
        repo = PlatformRepository(db)
        if repo.admin_count() > 0 or repo.get_user_by_email(PROCTORAI_BOOTSTRAP_ADMIN_EMAIL):
            return
        errors = validate_password(PROCTORAI_BOOTSTRAP_ADMIN_PASSWORD)
        if errors:
            return
        repo.create_user(
            PROCTORAI_BOOTSTRAP_ADMIN_EMAIL,
            "ProctorAI Administrator",
            "admin",
            hash_password(PROCTORAI_BOOTSTRAP_ADMIN_PASSWORD),
        )

    def _get_db():
        """Return a reusable DB connection for polling-heavy API endpoints."""
        global _db_connection, _db_retry_after, _bootstrap_checked
        try:
            from database.db_connection import DatabaseConnection
            now = time.monotonic()
            if _db_connection is None:
                _db_connection = DatabaseConnection()
            if not _db_connection.is_active:
                if now < _db_retry_after:
                    return None
                if not _db_connection.connect(max_retries=1):
                    _db_retry_after = time.monotonic() + 15
                    return None
                _db_retry_after = 0.0
                if not _bootstrap_checked:
                    _bootstrap_admin(_db_connection)
                    _bootstrap_checked = True
            return _db_connection
        except Exception:
            _db_connection = None
            _db_retry_after = time.monotonic() + 15
            return None

    def _repo():
        db = _get_db()
        if not db or not db.is_active:
            _api_error(503, "database_unavailable", "Database connection is required for this action.")
        from database.platform_repository import PlatformRepository
        return PlatformRepository(db)

    def _current_user(authorization: Optional[str] = Header(default=None)) -> dict:
        if not authorization or not authorization.lower().startswith("bearer "):
            _api_error(401, "not_authenticated", "Sign in is required.")
        token = authorization.split(" ", 1)[1].strip()
        try:
            from core.security import decode_access_token
            payload = decode_access_token(token)
        except RuntimeError as exc:
            _api_error(500, "auth_not_configured", str(exc))
        except Exception:
            _api_error(401, "invalid_token", "Your session expired or is invalid.")
        repo = _repo()
        user = repo.get_user(payload["sub"])
        if not user or not bool(user.get("is_active", True)):
            _api_error(401, "invalid_token", "Your account is not active.")
        return user

    def _require_roles(*roles: str):
        def dependency(user: dict = Depends(_current_user)) -> dict:
            if user.get("role") not in roles:
                _api_error(403, "forbidden", "Your role is not allowed to perform this action.")
            return user
        return dependency

    def _require_proctor_device(
        x_proctor_device_secret: Optional[str] = Header(default=None),
    ) -> dict:
        from config.settings import PROCTOR_DEVICE_SECRET

        if not x_proctor_device_secret or not hmac.compare_digest(
            x_proctor_device_secret,
            PROCTOR_DEVICE_SECRET,
        ):
            _api_error(401, "invalid_device_credential", "A valid proctor device credential is required.")
        return {"kind": "device"}

    def _browser_signal_principal(
        authorization: Optional[str] = Header(default=None),
        x_proctor_session_token: Optional[str] = Header(default=None),
        x_proctor_device_secret: Optional[str] = Header(default=None),
    ) -> dict:
        from config.settings import PROCTOR_DEVICE_SECRET

        if x_proctor_device_secret and hmac.compare_digest(x_proctor_device_secret, PROCTOR_DEVICE_SECRET):
            return {"kind": "device"}
        if x_proctor_session_token:
            try:
                from core.security import decode_browser_guard_token

                return {"kind": "browser_guard", "claims": decode_browser_guard_token(x_proctor_session_token)}
            except RuntimeError as exc:
                _api_error(500, "auth_not_configured", str(exc))
            except Exception:
                _api_error(401, "invalid_browser_guard_token", "The Browser Guard session token is invalid or expired.")
        if authorization:
            return {"kind": "user", "user": _current_user(authorization)}
        _api_error(401, "not_authenticated", "Browser signals require a signed-in student or trusted device.")

    def _public_user(user: dict) -> dict:
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

    def _tenant_id(user: dict | None = None) -> str:
        return str((user or {}).get("tenant_id") or "tenant_default")

    def _audit(
        action: str,
        *,
        actor: dict | None = None,
        resource_type: str = "",
        resource_id: str = "",
        details: dict | None = None,
        request: Request | None = None,
    ) -> None:
        try:
            repo = _repo()
            repo.write_audit_log(
                action,
                actor=actor,
                tenant_id=_tenant_id(actor),
                resource_type=resource_type,
                resource_id=resource_id,
                ip_address=request.client.host if request and request.client else "",
                user_agent=request.headers.get("user-agent", "") if request else "",
                details=details or {},
            )
        except Exception as exc:
            log_event(
                _api_logger,
                "audit.persist_failed",
                level="error",
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                error=exc.__class__.__name__,
            )

    def _parse_dt(value: Any) -> datetime:
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))

    def _b64url(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

    def _unb64url(data: str) -> bytes:
        return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))

    def _oauth_state() -> str:
        from core.security import require_auth_secret
        payload = {
            "nonce": secrets.token_urlsafe(18),
            "exp": int(time.time()) + 600,
            "provider": "google",
        }
        body = _b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
        sig = _b64url(hmac.new(require_auth_secret().encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest())
        return f"{body}.{sig}"

    def _verify_oauth_state(state: str) -> bool:
        try:
            from core.security import require_auth_secret
            body, sig = state.split(".", 1)
            expected = _b64url(hmac.new(require_auth_secret().encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest())
            if not hmac.compare_digest(sig, expected):
                return False
            payload = json.loads(_unb64url(body).decode("utf-8"))
            return payload.get("provider") == "google" and int(payload.get("exp", 0)) >= int(time.time())
        except Exception:
            return False

    def _frontend_oauth_error(code: str, message: str) -> RedirectResponse:
        from config.settings import FRONTEND_URL
        return RedirectResponse(f"{FRONTEND_URL}/login?oauth_error={quote(message)}&oauth_code={quote(code)}", status_code=302)

    def _frontend_oauth_success(session: dict) -> RedirectResponse:
        from config.settings import FRONTEND_URL
        payload = _b64url(json.dumps(session, default=str, separators=(",", ":")).encode("utf-8"))
        return RedirectResponse(f"{FRONTEND_URL}/oauth-callback#session={payload}", status_code=302)

    def _require_session_access(session_id: str, user: dict) -> None:
        db = _get_db()
        if not db or not db.is_active:
            row = _session_store.get(session_id)
            if not row:
                _api_error(503, "session_access_unavailable", "Session access cannot be verified while the database is unavailable.")
        else:
            rows = db.query("SELECT user_id, tenant_id, status FROM Sessions WHERE session_id = ?", (session_id,))
            if not rows:
                _api_error(404, "not_found", "Session not found.")
            row = rows[0]
        if user.get("role") == "admin":
            return
        if user.get("role") == "instructor":
            if not row.get("tenant_id") or row.get("tenant_id") != _tenant_id(user):
                _api_error(403, "forbidden", "This session belongs to another institution.")
            return
        if not row.get("user_id") or row.get("user_id") != user.get("user_id"):
            _api_error(403, "forbidden", "You can only access your own sessions.")

    def _authorized_browser_session(requested_session_id: str, principal: dict) -> str:
        active_session_id = _active_session_id()
        if principal.get("kind") == "device":
            session_id = requested_session_id or active_session_id
        elif principal.get("kind") == "browser_guard":
            claims = principal.get("claims") or {}
            session_id = str(claims.get("session_id") or "")
            if requested_session_id and requested_session_id != session_id:
                _api_error(403, "session_token_mismatch", "The Browser Guard token belongs to another session.")
            _require_session_access(
                session_id,
                {
                    "user_id": claims.get("sub"),
                    "tenant_id": claims.get("tenant_id"),
                    "role": "student",
                },
            )
        else:
            user = principal.get("user") or {}
            if user.get("role") != "student":
                _api_error(403, "forbidden", "Only the student exam client may submit browser signals.")
            session_id = requested_session_id or active_session_id
            _require_session_access(session_id, user)
        if not session_id:
            _api_error(409, "no_active_session", "No active proctoring session is available for this signal.")
        if not active_session_id or session_id != active_session_id:
            _api_error(409, "session_not_active", "Browser signals are accepted only for the active session.")
        return session_id

    # ── Health ────────────────────────────────────────────────

    @app.get("/health", response_model=HealthResponse)
    def health_check():
        return {"status": "healthy", "service": "proctorai-backend", "version": "1.0.0"}

    @app.get("/ops/status")
    def ops_status(user: dict = Depends(_require_roles("instructor", "admin"))):
        db = _get_db()
        model_path = Path(__import__("config.settings", fromlist=["PHONE_MODEL_PATH"]).PHONE_MODEL_PATH)
        return {
            "status": "ok",
            "environment": APP_ENV,
            "version": "1.0.0",
            "uptime_seconds": int(time.time() - _app_started_at),
            "python": sys.version.split()[0],
            "database": {
                "connected": bool(db and db.is_active),
                "name": __import__("config.settings", fromlist=["DB_NAME"]).DB_NAME,
                "driver": __import__("config.settings", fromlist=["DB_DRIVER"]).DB_DRIVER,
            },
            "storage": {
                "logs_dir": LOGS_DIR,
                "reports_dir": __import__("config.settings", fromlist=["REPORTS_DIR"]).REPORTS_DIR,
                "screenshots_dir": __import__("config.settings", fromlist=["SCREENSHOTS_DIR"]).SCREENSHOTS_DIR,
            },
            "proctoring": {
                "phone_model_available": model_path.exists(),
                "browser_guard_active": (time.time() - _guard_last_seen) < 15,
            },
            "auth": {
                "role": user.get("role"),
                "tenant_id": _tenant_id(user),
            },
        }

    @app.get("/ops/metrics")
    def ops_metrics(user: dict = Depends(_require_roles("admin"))):
        metrics = _repo().dashboard_metrics(_tenant_id(user))
        metrics.update(
            {
                "uptime_seconds": int(time.time() - _app_started_at),
                "in_memory_events": len(_events),
                "in_memory_browser_events": len(_browser_events),
                "active_session_id": _active_session_id(),
            }
        )
        return metrics

    @app.post("/auth/register", response_model=AuthResponse)
    def register(req: RegisterRequest, request: Request):
        email = (req.email or "").strip().lower()
        full_name = (req.full_name or "").strip()
        if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
            _api_error(422, "validation_error", "Enter a valid email address.")
        if len(full_name) < 2:
            _api_error(422, "validation_error", "Enter your full name.")
        from core.security import create_access_token, hash_password, validate_password
        errors = validate_password(req.password)
        if errors:
            _api_error(422, "validation_error", "Password does not meet requirements.", errors)
        repo = _repo()
        if repo.get_user_by_email(email):
            _api_error(409, "email_exists", "An account with this email already exists.")
        user = repo.create_user(email, full_name, "student", hash_password(req.password))
        _audit("auth.register", actor=user, resource_type="user", resource_id=user["user_id"], request=request)
        return {"access_token": create_access_token(user), "token_type": "bearer", "user": _public_user(user)}

    @app.post("/auth/login", response_model=AuthResponse)
    def login(req: LoginRequest, request: Request):
        repo = _repo()
        user = repo.get_user_by_email((req.email or "").strip().lower())
        from core.security import create_access_token, verify_password
        if not user or not verify_password(req.password, user.get("password_hash", "")):
            _api_error(401, "invalid_credentials", "Email or password is incorrect.")
        if not bool(user.get("is_active", True)):
            _api_error(403, "account_disabled", "This account is disabled.")
        _audit("auth.login", actor=user, resource_type="user", resource_id=user["user_id"], request=request)
        return {"access_token": create_access_token(user), "token_type": "bearer", "user": _public_user(user)}

    @app.get("/auth/me", response_model=UserPublic)
    def auth_me(user: dict = Depends(_current_user)):
        return _public_user(user)

    @app.post("/auth/logout")
    def auth_logout(request: Request, user: dict = Depends(_current_user)):
        _audit("auth.logout", actor=user, resource_type="user", resource_id=user["user_id"], request=request)
        return {"status": "ok"}

    @app.post("/auth/forgot-password")
    def forgot_password(req: ForgotPasswordRequest, request: Request):
        from config.settings import FRONTEND_URL
        from core.email_service import EmailConfigurationError, send_password_reset_email, smtp_configured
        if not smtp_configured():
            _api_error(503, "email_not_configured", "Password reset email is not configured.")
        repo = _repo()
        user = repo.get_user_by_email((req.email or "").strip().lower())
        if not user:
            _api_error(404, "email_not_found", "No account exists for that email address.")
        from core.security import create_reset_token
        token, token_hash, expires_at = create_reset_token()
        repo.create_reset_token(user["user_id"], token_hash, expires_at)
        reset_url = f"{FRONTEND_URL}/reset-password?token={token}"
        try:
            send_password_reset_email(user["email"], reset_url)
        except EmailConfigurationError as exc:
            _api_error(503, "email_not_configured", str(exc) or "Password reset email is not configured.")
        except Exception:
            _api_error(502, "email_delivery_failed", "Could not send the reset email.")
        _audit("auth.password_reset_requested", actor=user, resource_type="user", resource_id=user["user_id"], request=request)
        return {"status": "ok"}

    @app.post("/auth/reset-password")
    def reset_password(req: ResetPasswordRequest, request: Request):
        from core.security import hash_password, hash_reset_token, validate_password
        errors = validate_password(req.password)
        if errors:
            _api_error(422, "validation_error", "Password does not meet requirements.", errors)
        repo = _repo()
        row = repo.get_reset_token(hash_reset_token(req.token))
        if not row:
            _api_error(400, "invalid_reset_token", "The reset link is invalid.")
        if row.get("used_at"):
            _api_error(400, "reset_token_used", "The reset link has already been used.")
        try:
            expires_at = _parse_dt(row.get("expires_at"))
        except Exception:
            _api_error(400, "invalid_reset_token", "The reset link is invalid.")
        if expires_at < datetime.now(expires_at.tzinfo or timezone.utc):
            _api_error(400, "reset_token_expired", "The reset link has expired.")
        repo.update_password(row["user_id"], hash_password(req.password))
        repo.mark_reset_token_used(row["token_id"])
        user = repo.get_user(row["user_id"])
        _audit("auth.password_reset_completed", actor=user, resource_type="user", resource_id=row["user_id"], request=request)
        return {"status": "ok"}

    @app.get("/auth/google/start")
    def google_auth_start():
        from config.settings import GOOGLE_CLIENT_ID, GOOGLE_REDIRECT_URI
        if not GOOGLE_CLIENT_ID:
            return _frontend_oauth_error("google_not_configured", "Google sign-in is not configured.")
        params = urlencode(
            {
                "client_id": GOOGLE_CLIENT_ID,
                "redirect_uri": GOOGLE_REDIRECT_URI,
                "response_type": "code",
                "scope": "openid email profile",
                "state": _oauth_state(),
                "access_type": "online",
                "prompt": "select_account",
            }
        )
        return RedirectResponse(f"https://accounts.google.com/o/oauth2/v2/auth?{params}", status_code=302)

    @app.get("/auth/google/callback")
    def google_auth_callback(code: str = "", state: str = "", error: str = ""):
        from config.settings import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI
        if error:
            return _frontend_oauth_error("google_denied", "Google sign-in was cancelled.")
        if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
            return _frontend_oauth_error("google_not_configured", "Google sign-in is not configured.")
        if not code or not state or not _verify_oauth_state(state):
            return _frontend_oauth_error("invalid_oauth_state", "Google sign-in session expired. Try again.")

        try:
            token_body = urlencode(
                {
                    "code": code,
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "redirect_uri": GOOGLE_REDIRECT_URI,
                    "grant_type": "authorization_code",
                }
            ).encode("utf-8")
            token_req = urlrequest.Request(
                "https://oauth2.googleapis.com/token",
                data=token_body,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                method="POST",
            )
            with urlrequest.urlopen(token_req, timeout=12) as resp:
                token_payload = json.loads(resp.read().decode("utf-8"))
            id_token = token_payload.get("id_token")
            if not id_token:
                return _frontend_oauth_error("google_token_missing", "Google did not return an identity token.")

            with urlrequest.urlopen(
                f"https://oauth2.googleapis.com/tokeninfo?id_token={quote(id_token)}",
                timeout=12,
            ) as resp:
                claims = json.loads(resp.read().decode("utf-8"))
        except Exception:
            return _frontend_oauth_error("google_exchange_failed", "Could not verify your Google account.")

        if claims.get("aud") != GOOGLE_CLIENT_ID or claims.get("email_verified") not in {True, "true", "True", "1"}:
            return _frontend_oauth_error("google_identity_invalid", "Google account verification failed.")

        email = str(claims.get("email") or "").strip().lower()
        full_name = str(claims.get("name") or email.split("@", 1)[0] or "Google User").strip()
        if not email:
            return _frontend_oauth_error("google_email_missing", "Google did not provide an email address.")

        from core.security import create_access_token, hash_password
        repo = _repo()
        user = repo.get_user_by_email(email)
        if user and not bool(user.get("is_active", True)):
            return _frontend_oauth_error("account_disabled", "This account is disabled.")
        if user:
            action = "auth.google_login"
        else:
            user = repo.create_user(email, full_name, "student", hash_password(secrets.token_urlsafe(32)))
            action = "auth.google_register"
        _audit(action, actor=user, resource_type="user", resource_id=user["user_id"])
        return _frontend_oauth_success(
            {
                "access_token": create_access_token(user),
                "token_type": "bearer",
                "user": _public_user(user),
            }
        )

    def _format_exam(row: dict) -> dict:
        rules = row.get("rules_json") or row.get("rules") or {}
        if isinstance(rules, str):
            try:
                rules = json.loads(rules)
            except Exception:
                rules = {"policy": rules}
        return {
            "exam_id": row.get("exam_id"),
            "tenant_id": row.get("tenant_id") or "tenant_default",
            "exam_code": row.get("exam_code") or "",
            "title": row.get("title"),
            "description": row.get("description") or "",
            "semester": row.get("semester") or "",
            "subject": row.get("subject") or "",
            "department": row.get("department") or "",
            "total_marks": int(row.get("total_marks") or 0),
            "duration_minutes": int(row.get("duration_minutes") or 60),
            "start_time": _iso(row.get("start_time")) if row.get("start_time") else None,
            "end_time": _iso(row.get("end_time")) if row.get("end_time") else None,
            "status": row.get("status") or "draft",
            "rules": rules,
            "assignment_id": row.get("assignment_id"),
            "assignment_status": row.get("assignment_status"),
            "assignment_count": int(row.get("assignment_count") or 0),
        }

    def _validate_exam_status(status: str) -> str:
        status = (status or "draft").strip().lower()
        if status not in {"draft", "published", "scheduled", "archived", "closed"}:
            _api_error(422, "validation_error", "Exam status must be draft, scheduled, published, closed, or archived.")
        return status

    def _exam_payload(req: ExamRequest) -> dict:
        data = req.model_dump()
        data["exam_code"] = "".join(ch for ch in (data.get("exam_code") or "").upper().strip() if ch.isalnum() or ch in "-_")
        data["title"] = (data.get("title") or "").strip()
        data["description"] = (data.get("description") or "").strip()
        data["semester"] = (data.get("semester") or "").strip()
        data["subject"] = (data.get("subject") or "").strip()
        data["department"] = (data.get("department") or "").strip()
        if not data["title"]:
            _api_error(422, "validation_error", "Exam title is required.")
        if int(data.get("total_marks") or 0) < 0:
            _api_error(422, "validation_error", "Total marks cannot be negative.")
        data["status"] = _validate_exam_status(data.get("status") or "draft")
        rules = data.get("rules")
        if rules is None:
            data["rules"] = {}
        elif isinstance(rules, str):
            data["rules"] = {"policy": rules.strip()} if rules.strip() else {}
        elif not isinstance(rules, dict):
            _api_error(422, "validation_error", "Exam rules must be text or a JSON object.")
        if int(data.get("duration_minutes") or 0) < 1:
            _api_error(422, "validation_error", "Exam duration must be at least one minute.")
        if data.get("start_time") and data.get("end_time"):
            try:
                if _parse_dt(data["end_time"]) <= _parse_dt(data["start_time"]):
                    _api_error(422, "validation_error", "Exam end time must be after start time.")
            except HTTPException:
                raise
            except Exception:
                _api_error(422, "validation_error", "Exam start/end times must be valid ISO date strings.")
        return data

    def _require_exam_window(exam: dict) -> None:
        now = datetime.now(timezone.utc)
        try:
            if exam.get("start_time") and now < _parse_dt(exam["start_time"]):
                _api_error(403, "exam_not_started", "This exam is not open yet.")
            if exam.get("end_time") and now >= _parse_dt(exam["end_time"]):
                _api_error(403, "exam_closed", "This exam window has closed.")
        except HTTPException:
            raise
        except Exception:
            _api_error(500, "invalid_exam_schedule", "The exam schedule is invalid. Ask the instructor to correct it.")

    def _attempt_expired(attempt: dict) -> bool:
        if not attempt.get("started_at"):
            return False
        try:
            duration = max(1, int(attempt.get("duration_minutes") or 60))
            return datetime.now(timezone.utc) >= _parse_dt(attempt["started_at"]) + timedelta(minutes=duration)
        except Exception:
            return False

    def _format_question(row: dict, *, include_correct: bool = True) -> dict:
        options = []
        for option in row.get("options") or []:
            payload = {
                "option_id": option.get("option_id"),
                "question_id": option.get("question_id"),
                "option_text": option.get("option_text") or "",
                "sort_order": int(option.get("sort_order") or 0),
            }
            if include_correct:
                payload["is_correct"] = bool(option.get("is_correct"))
            options.append(payload)
        return {
            "question_id": row.get("question_id"),
            "tenant_id": row.get("tenant_id") or "tenant_default",
            "exam_id": row.get("exam_id"),
            "question_text": row.get("question_text") or "",
            "question_type": row.get("question_type") or "mcq",
            "marks": int(row.get("marks") or 1),
            "sort_order": int(row.get("sort_order") or 0),
            "status": row.get("status") or "active",
            "options": options,
        }

    def _question_payload(req: ExamQuestionRequest) -> dict:
        data = req.model_dump()
        data["question_text"] = (data.get("question_text") or "").strip()
        data["question_type"] = (data.get("question_type") or "mcq").strip().lower()
        if data["question_type"] != "mcq":
            _api_error(422, "validation_error", "Only MCQ questions are supported in this version.")
        if len(data["question_text"]) < 3:
            _api_error(422, "validation_error", "Question text is required.")
        if int(data.get("marks") or 0) < 1:
            _api_error(422, "validation_error", "Question marks must be at least 1.")
        options = data.get("options") or []
        clean_options = []
        for index, option in enumerate(options):
            text = str(option.get("option_text") or "").strip()
            if not text:
                continue
            clean_options.append({
                "option_id": option.get("option_id") or "",
                "option_text": text,
                "is_correct": bool(option.get("is_correct")),
                "sort_order": int(option.get("sort_order") if option.get("sort_order") is not None else index),
            })
        if len(clean_options) < 2:
            _api_error(422, "validation_error", "Add at least two answer options.")
        if not any(option["is_correct"] for option in clean_options):
            _api_error(422, "validation_error", "Mark one option as correct.")
        data["options"] = clean_options
        return data

    def _validate_exam_content(exam_id: str, declared_marks: int = 0) -> int:
        questions = _repo().list_exam_questions(exam_id, include_correct=True)
        if not questions:
            _api_error(422, "validation_error", "Add at least one valid question before publishing or scheduling.")
        question_marks = sum(int(question.get("marks") or 0) for question in questions)
        if declared_marks not in {0, question_marks}:
            _api_error(
                422,
                "marks_mismatch",
                f"Declared total marks ({declared_marks}) must match the question total ({question_marks}).",
            )
        return question_marks

    def _require_exam_content_editable(exam: dict) -> None:
        if (exam.get("status") or "draft").lower() in {"published", "scheduled"}:
            _api_error(
                409,
                "exam_content_locked",
                "Return the exam to draft status before changing published questions or options.",
            )

    def _format_attempt_response(row: dict, *, include_grading: bool = False) -> dict:
        payload = {
            "response_id": row.get("response_id"),
            "attempt_id": row.get("attempt_id"),
            "question_id": row.get("question_id"),
            "selected_option_id": row.get("selected_option_id"),
            "response_text": row.get("response_text"),
            "answered_at": _iso(row.get("answered_at")) if row.get("answered_at") else None,
            "updated_at": _iso(row.get("updated_at")) if row.get("updated_at") else None,
        }
        if include_grading:
            payload["is_correct"] = bool(row.get("is_correct")) if row.get("is_correct") is not None else None
            payload["awarded_marks"] = int(row.get("awarded_marks") or 0)
        return payload

    def _format_attempt(
        row: dict,
        *,
        questions: list[dict] | None = None,
        responses: list[dict] | None = None,
        include_response_grading: bool = False,
    ) -> dict:
        return {
            "attempt_id": row.get("attempt_id"),
            "tenant_id": row.get("tenant_id") or "tenant_default",
            "exam_id": row.get("exam_id"),
            "assignment_id": row.get("assignment_id"),
            "session_id": row.get("session_id"),
            "user_id": row.get("user_id"),
            "roll_number": row.get("roll_number") or "",
            "status": row.get("status") or "in_progress",
            "started_at": _iso(row.get("started_at")) if row.get("started_at") else None,
            "submitted_at": _iso(row.get("submitted_at")) if row.get("submitted_at") else None,
            "score": int(row.get("score") or 0),
            "max_score": int(row.get("max_score") or 0),
            "risk_score": min(int(row.get("risk_score") or 0), 100),
            "exam": {
                "id": row.get("exam_id"),
                "exam_code": row.get("exam_code") or "",
                "title": row.get("exam_title") or "",
                "duration_minutes": int(row.get("duration_minutes") or 60),
                "total_marks": int(row.get("total_marks") or row.get("max_score") or 0),
            },
            "student": {
                "id": row.get("user_id"),
                "name": row.get("student_name") or "",
                "email": row.get("student_email") or "",
            },
            "questions": questions or [],
            "responses": [
                _format_attempt_response(response, include_grading=include_response_grading)
                for response in (responses or [])
            ],
        }

    def _require_exam_management_access(exam_id: str, user: dict) -> dict:
        repo = _repo()
        row = repo.get_exam(exam_id)
        if not row:
            _api_error(404, "not_found", "Exam not found.")
        if user.get("role") != "admin" and (row.get("tenant_id") or "tenant_default") != _tenant_id(user):
            _api_error(403, "forbidden", "This exam belongs to another institution.")
        return row

    def _format_assignment(row: dict) -> dict:
        return {
            "assignment_id": row.get("assignment_id"),
            "tenant_id": row.get("tenant_id") or "tenant_default",
            "exam_id": row.get("exam_id"),
            "student_user_id": row.get("student_user_id"),
            "student_email": row.get("student_email") or "",
            "student_name": row.get("student_name") or "",
            "student_active": bool(row.get("student_active", True)),
            "assigned_at": _iso(row.get("assigned_at")) if row.get("assigned_at") else None,
            "status": row.get("status") or "assigned",
        }

    @app.get("/exams")
    def list_exams(user: dict = Depends(_require_roles("instructor", "admin"))):
        return [_format_exam(row) for row in _repo().list_exams(user)]

    @app.post("/exams")
    def create_exam(req: ExamRequest, request: Request, user: dict = Depends(_require_roles("instructor", "admin"))):
        payload = _exam_payload(req)
        if payload["status"] in {"published", "scheduled"}:
            _api_error(422, "validation_error", "Create the exam as a draft, add questions, then publish or schedule it.")
        exam = _repo().create_exam(payload, user["user_id"], _tenant_id(user))
        _audit("exam.created", actor=user, resource_type="exam", resource_id=exam.get("exam_id", ""), request=request)
        return _format_exam(exam)

    @app.get("/exams/{exam_id}")
    def get_exam(exam_id: str, user: dict = Depends(_current_user)):
        repo = _repo()
        row = repo.get_exam(exam_id)
        if not row:
            _api_error(404, "not_found", "Exam not found.")
        if user["role"] == "student" and not repo.exam_assigned_to_student(exam_id, user["user_id"]):
            _api_error(403, "forbidden", "This exam is not assigned to you.")
        if user["role"] == "instructor" and (row.get("tenant_id") or "tenant_default") != _tenant_id(user):
            _api_error(403, "forbidden", "This exam belongs to another institution.")
        return _format_exam(row)

    @app.put("/exams/{exam_id}")
    def update_exam(exam_id: str, req: ExamRequest, request: Request, user: dict = Depends(_require_roles("instructor", "admin"))):
        _require_exam_management_access(exam_id, user)
        repo = _repo()
        payload = _exam_payload(req)
        if payload["status"] in {"published", "scheduled"}:
            question_marks = _validate_exam_content(exam_id, int(payload.get("total_marks") or 0))
            if int(payload.get("total_marks") or 0) == 0:
                payload["total_marks"] = question_marks
        row = repo.update_exam(exam_id, payload)
        if not row:
            _api_error(404, "not_found", "Exam not found.")
        _audit("exam.updated", actor=user, resource_type="exam", resource_id=exam_id, request=request)
        return _format_exam(row)

    @app.post("/exams/{exam_id}/publish")
    def publish_exam(exam_id: str, request: Request, user: dict = Depends(_require_roles("instructor", "admin"))):
        repo = _repo()
        exam = _require_exam_management_access(exam_id, user)
        declared_marks = int(exam.get("total_marks") or 0)
        question_marks = _validate_exam_content(exam_id, declared_marks)
        if declared_marks == 0:
            repo.update_exam(exam_id, {"total_marks": question_marks})
        row = repo.publish_exam(exam_id)
        _audit("exam.published", actor=user, resource_type="exam", resource_id=exam_id, request=request)
        return _format_exam(row)

    @app.get("/exams/{exam_id}/questions")
    def list_exam_questions(exam_id: str, user: dict = Depends(_current_user)):
        repo = _repo()
        row = repo.get_exam(exam_id)
        if not row:
            _api_error(404, "not_found", "Exam not found.")
        include_correct = user["role"] in {"instructor", "admin"}
        if user["role"] == "student" and not repo.exam_assigned_to_student(exam_id, user["user_id"]):
            _api_error(403, "forbidden", "This exam is not assigned to you.")
        if user["role"] == "instructor" and (row.get("tenant_id") or "tenant_default") != _tenant_id(user):
            _api_error(403, "forbidden", "This exam belongs to another institution.")
        return [_format_question(question, include_correct=include_correct) for question in repo.list_exam_questions(exam_id, include_correct=include_correct)]

    @app.post("/exams/{exam_id}/questions")
    def create_exam_question(exam_id: str, req: ExamQuestionRequest, request: Request, user: dict = Depends(_require_roles("instructor", "admin"))):
        repo = _repo()
        exam = _require_exam_management_access(exam_id, user)
        _require_exam_content_editable(exam)
        question = repo.upsert_question(exam_id, _question_payload(req), exam.get("tenant_id") or _tenant_id(user))
        _audit("exam.question_saved", actor=user, resource_type="exam", resource_id=exam_id, request=request)
        questions = [q for q in repo.list_exam_questions(exam_id, include_correct=True) if q.get("question_id") == question.get("question_id")]
        return _format_question(questions[0]) if questions else _format_question(question)

    @app.put("/exams/{exam_id}/questions/{question_id}")
    def update_exam_question(exam_id: str, question_id: str, req: ExamQuestionRequest, request: Request, user: dict = Depends(_require_roles("instructor", "admin"))):
        repo = _repo()
        exam = _require_exam_management_access(exam_id, user)
        _require_exam_content_editable(exam)
        existing = repo.get_question(question_id)
        if not existing or existing.get("exam_id") != exam_id:
            _api_error(404, "not_found", "Question not found.")
        repo.upsert_question(exam_id, _question_payload(req), exam.get("tenant_id") or _tenant_id(user), question_id)
        questions = [q for q in repo.list_exam_questions(exam_id, include_correct=True) if q.get("question_id") == question_id]
        _audit("exam.question_saved", actor=user, resource_type="question", resource_id=question_id, request=request)
        return _format_question(questions[0]) if questions else {}

    @app.delete("/exams/{exam_id}/questions/{question_id}")
    def delete_exam_question(exam_id: str, question_id: str, request: Request, user: dict = Depends(_require_roles("instructor", "admin"))):
        repo = _repo()
        exam = _require_exam_management_access(exam_id, user)
        _require_exam_content_editable(exam)
        existing = repo.get_question(question_id)
        if not existing or existing.get("exam_id") != exam_id:
            _api_error(404, "not_found", "Question not found.")
        repo.delete_question(question_id)
        _audit("exam.question_deleted", actor=user, resource_type="question", resource_id=question_id, request=request)
        return {"status": "ok", "question_id": question_id}

    @app.post("/questions/{question_id}/options")
    def create_question_option(question_id: str, req: QuestionOptionRequest, request: Request, user: dict = Depends(_require_roles("instructor", "admin"))):
        repo = _repo()
        question = repo.get_question(question_id)
        if not question:
            _api_error(404, "not_found", "Question not found.")
        exam = _require_exam_management_access(question["exam_id"], user)
        _require_exam_content_editable(exam)
        text = (req.option_text or "").strip()
        if not text:
            _api_error(422, "validation_error", "Option text is required.")
        option = repo.upsert_option(question_id, {**req.model_dump(), "option_text": text}, question.get("tenant_id") or _tenant_id(user))
        _audit("question.option_saved", actor=user, resource_type="question", resource_id=question_id, request=request)
        return option

    @app.put("/questions/{question_id}/options/{option_id}")
    def update_question_option(question_id: str, option_id: str, req: QuestionOptionRequest, request: Request, user: dict = Depends(_require_roles("instructor", "admin"))):
        repo = _repo()
        question = repo.get_question(question_id)
        if not question:
            _api_error(404, "not_found", "Question not found.")
        exam = _require_exam_management_access(question["exam_id"], user)
        _require_exam_content_editable(exam)
        text = (req.option_text or "").strip()
        if not text:
            _api_error(422, "validation_error", "Option text is required.")
        option = repo.upsert_option(question_id, {**req.model_dump(), "option_text": text}, question.get("tenant_id") or _tenant_id(user), option_id)
        _audit("question.option_saved", actor=user, resource_type="option", resource_id=option_id, request=request)
        return option

    @app.delete("/questions/{question_id}/options/{option_id}")
    def delete_question_option(question_id: str, option_id: str, request: Request, user: dict = Depends(_require_roles("instructor", "admin"))):
        repo = _repo()
        question = repo.get_question(question_id)
        if not question:
            _api_error(404, "not_found", "Question not found.")
        exam = _require_exam_management_access(question["exam_id"], user)
        _require_exam_content_editable(exam)
        option = repo.get_option(option_id)
        if not option or option.get("question_id") != question_id:
            _api_error(404, "not_found", "Option not found.")
        repo.delete_option(option_id)
        _audit("question.option_deleted", actor=user, resource_type="option", resource_id=option_id, request=request)
        return {"status": "ok", "option_id": option_id}

    @app.post("/exams/{exam_id}/assignments")
    def assign_exam(exam_id: str, req: AssignmentRequest, request: Request, user: dict = Depends(_require_roles("instructor", "admin"))):
        repo = _repo()
        exam = _require_exam_management_access(exam_id, user)
        student = repo.get_user_by_email((req.student_email or "").strip().lower())
        if not student or student.get("role") != "student":
            _api_error(404, "student_not_found", "A student account with that email was not found.")
        if (student.get("tenant_id") or "tenant_default") != (exam.get("tenant_id") or _tenant_id(user)):
            _api_error(403, "forbidden", "Student must belong to the same institution as the exam.")
        assignment = repo.assign_exam(exam_id, student["user_id"], user["user_id"], exam.get("tenant_id") or _tenant_id(user))
        _audit(
            "exam.assigned",
            actor=user,
            resource_type="exam",
            resource_id=exam_id,
            details={"student_user_id": student["user_id"]},
            request=request,
        )
        return assignment

    @app.get("/exams/{exam_id}/assignments", response_model=List[AssignmentItem])
    def list_exam_assignments(exam_id: str, user: dict = Depends(_require_roles("instructor", "admin"))):
        _require_exam_management_access(exam_id, user)
        return [_format_assignment(row) for row in _repo().list_exam_assignments(exam_id)]

    @app.delete("/exams/{exam_id}/assignments/{assignment_id}")
    def revoke_exam_assignment(
        exam_id: str,
        assignment_id: str,
        request: Request,
        user: dict = Depends(_require_roles("instructor", "admin")),
    ):
        _require_exam_management_access(exam_id, user)
        row = _repo().revoke_assignment(assignment_id)
        if not row or row.get("exam_id") != exam_id:
            _api_error(404, "not_found", "Assignment not found.")
        _audit(
            "exam.assignment_revoked",
            actor=user,
            resource_type="exam",
            resource_id=exam_id,
            details={"assignment_id": assignment_id, "student_user_id": row.get("student_user_id")},
            request=request,
        )
        return {"status": "ok", "assignment_id": assignment_id}

    @app.get("/student/exams")
    def student_exams(user: dict = Depends(_require_roles("student"))):
        return [_format_exam(row) for row in _repo().list_exams(user)]

    @app.post("/student/exams/join-code")
    def join_exam_by_code(req: ExamCodeJoinRequest, request: Request, user: dict = Depends(_require_roles("student"))):
        repo = _repo()
        code = (req.exam_code or "").strip()
        if not code:
            _api_error(422, "validation_error", "Enter an exam code.")
        exam = repo.get_exam_by_code(code, _tenant_id(user))
        if not exam:
            _api_error(404, "not_found", "No published exam was found for that code.")
        if (exam.get("status") or "").lower() not in {"published", "scheduled"}:
            _api_error(403, "exam_unavailable", "This exam code is not open for students.")
        assignment = repo.ensure_code_assignment(exam["exam_id"], user["user_id"], exam.get("tenant_id") or _tenant_id(user))
        _audit(
            "exam.code_joined",
            actor=user,
            resource_type="exam",
            resource_id=exam["exam_id"],
            details={"exam_code": code, "assignment_id": assignment.get("assignment_id")},
            request=request,
        )
        return {**_format_exam({**exam, "assignment_id": assignment.get("assignment_id"), "assignment_status": assignment.get("status") or "assigned"}), "assignment_id": assignment.get("assignment_id")}

    @app.post("/attempts/start")
    def start_attempt(req: AttemptStartRequest, request: Request, user: dict = Depends(_require_roles("student"))):
        repo = _repo()
        exam = repo.get_exam(req.exam_id)
        if not exam:
            _api_error(404, "not_found", "Exam not found.")
        if (exam.get("status") or "").lower() not in {"published", "scheduled"}:
            _api_error(403, "exam_unavailable", "This exam is not open for attempts.")
        _require_exam_window(exam)
        assignment = repo.assignment_for_student(req.exam_id, user["user_id"])
        if not assignment:
            _api_error(403, "forbidden", "This exam is not assigned to you. Join by exam code first if your instructor provided one.")
        roll_number = (req.roll_number or "").strip()
        if len(roll_number) < 2:
            _api_error(422, "validation_error", "Official university roll number is required.")
        submitted = repo.submitted_attempt_for_student(req.exam_id, user["user_id"])
        if submitted:
            _api_error(409, "attempt_locked", "This exam has already been submitted. Reattempt is locked.")
        active = repo.active_attempt_for_student(req.exam_id, user["user_id"])
        if active and _attempt_expired({**active, "duration_minutes": exam.get("duration_minutes")}):
            repo.submit_attempt(active["attempt_id"])
            if active.get("session_id"):
                _write_active_proctor_state(False)
                _clear_active_session(active.get("session_id"))
            _api_error(409, "attempt_locked", "The previous attempt reached its time limit and was submitted automatically.")
        if active:
            attempt = active
        else:
            from core.security import new_id
            session_id = req.session_id or new_id("session")
            attempt = repo.create_attempt(
                exam_id=req.exam_id,
                user_id=user["user_id"],
                roll_number=roll_number,
                assignment_id=assignment.get("assignment_id") or "",
                session_id=session_id,
                tenant_id=exam.get("tenant_id") or _tenant_id(user),
            )
            from database.student_repository import StudentRepository
            db = _get_db()
            if db and db.is_active:
                StudentRepository(db).upsert_session(
                    session_id,
                    student_id=user["user_id"],
                    student_name=user.get("full_name", ""),
                    exam_code=exam.get("exam_code") or exam.get("title") or req.exam_id,
                    user_id=user["user_id"],
                    exam_id=req.exam_id,
                    roll_number=roll_number,
                    tenant_id=exam.get("tenant_id") or _tenant_id(user),
                    start_time=datetime.now(timezone.utc),
                    status="Active",
                )
            _session_meta.update({
                "session_id": session_id,
                "student_id": user["user_id"],
                "exam_code": exam.get("exam_code") or req.exam_id,
                "user_id": user["user_id"],
                "started_at": datetime.now(timezone.utc).isoformat(),
            })
            _session_store[session_id] = {
                "session_id": session_id,
                "user_id": user["user_id"],
                "student_id": user["user_id"],
                "student_name": user.get("full_name", ""),
                "roll_number": roll_number,
                "exam_id": req.exam_id,
                "exam_code": exam.get("exam_code") or "",
                "tenant_id": exam.get("tenant_id") or _tenant_id(user),
                "status": "Active",
                "started_at": datetime.now(timezone.utc).isoformat(),
            }
            _write_active_proctor_state(True, session_id, user["user_id"], exam.get("exam_code") or req.exam_id)
        questions = [_format_question(q, include_correct=False) for q in repo.list_exam_questions(req.exam_id, include_correct=False)]
        responses = repo.get_attempt_responses(attempt["attempt_id"])
        _audit("attempt.started", actor=user, resource_type="attempt", resource_id=attempt["attempt_id"], request=request)
        return _format_attempt(attempt, questions=questions, responses=responses)

    @app.get("/attempts/{attempt_id}")
    def get_attempt(attempt_id: str, user: dict = Depends(_current_user)):
        repo = _repo()
        attempt = repo.get_attempt(attempt_id)
        if not attempt:
            _api_error(404, "not_found", "Attempt not found.")
        if user["role"] == "student" and attempt.get("user_id") != user["user_id"]:
            _api_error(403, "forbidden", "You can only access your own attempts.")
        if user["role"] == "instructor" and (attempt.get("tenant_id") or "tenant_default") != _tenant_id(user):
            _api_error(403, "forbidden", "This attempt belongs to another institution.")
        if attempt.get("status") == "in_progress" and _attempt_expired(attempt):
            attempt = repo.submit_attempt(attempt_id) or attempt
            if attempt.get("session_id"):
                _write_active_proctor_state(False)
                _clear_active_session(attempt.get("session_id"))
        include_correct = user["role"] in {"instructor", "admin"}
        questions = [_format_question(q, include_correct=include_correct) for q in repo.list_exam_questions(attempt["exam_id"], include_correct=include_correct)]
        responses = repo.get_attempt_responses(attempt_id)
        return _format_attempt(
            attempt,
            questions=questions,
            responses=responses,
            include_response_grading=include_correct,
        )

    @app.post("/attempts/{attempt_id}/responses")
    def save_attempt_response(attempt_id: str, req: AttemptResponseRequest, request: Request, user: dict = Depends(_require_roles("student"))):
        repo = _repo()
        attempt = repo.get_attempt(attempt_id)
        if not attempt:
            _api_error(404, "not_found", "Attempt not found.")
        if attempt.get("user_id") != user["user_id"]:
            _api_error(403, "forbidden", "You can only update your own attempt.")
        if attempt.get("status") == "submitted":
            _api_error(409, "attempt_locked", "This attempt has already been submitted.")
        if _attempt_expired(attempt):
            repo.submit_attempt(attempt_id)
            if attempt.get("session_id"):
                _write_active_proctor_state(False)
                _clear_active_session(attempt.get("session_id"))
            _api_error(409, "attempt_expired", "The exam time limit was reached and the attempt was submitted automatically.")
        question = repo.get_question(req.question_id)
        if not question or question.get("exam_id") != attempt.get("exam_id"):
            _api_error(404, "not_found", "Question not found for this attempt.")
        if req.selected_option_id:
            option = repo.get_option(req.selected_option_id)
            if not option or option.get("question_id") != req.question_id:
                _api_error(422, "validation_error", "Selected option does not belong to this question.")
        response = repo.save_response(
            attempt_id=attempt_id,
            question_id=req.question_id,
            selected_option_id=req.selected_option_id,
            response_text=req.response_text,
            tenant_id=attempt.get("tenant_id") or _tenant_id(user),
        )
        _audit("attempt.response_saved", actor=user, resource_type="attempt", resource_id=attempt_id, details={"question_id": req.question_id}, request=request)
        return _format_attempt_response(response, include_grading=False)

    @app.post("/attempts/{attempt_id}/submit")
    def submit_attempt(attempt_id: str, req: AttemptSubmitRequest, request: Request, user: dict = Depends(_require_roles("student"))):
        repo = _repo()
        attempt = repo.get_attempt(attempt_id)
        if not attempt:
            _api_error(404, "not_found", "Attempt not found.")
        if attempt.get("user_id") != user["user_id"]:
            _api_error(403, "forbidden", "You can only submit your own attempt.")
        if attempt.get("status") == "submitted":
            _api_error(409, "attempt_locked", "This attempt has already been submitted.")
        submitted = repo.submit_attempt(attempt_id)
        if not submitted:
            _api_error(500, "submit_failed", "Could not submit attempt.")
        if submitted.get("session_id"):
            submitted = dict(submitted)
            submitted["risk_score"] = min(
                sum(int(row.get("risk_points") or 0) for row in _get_session_events(submitted["session_id"])),
                100,
            )
        if submitted.get("session_id"):
            _write_active_proctor_state(False)
            _clear_active_session(submitted.get("session_id"))
        report = None
        if req.generate_report and submitted.get("session_id"):
            try:
                path = _generate_report_file(submitted["session_id"])
                report = _report_metadata(submitted["session_id"], path)
            except Exception:
                report = None
        _audit("attempt.submitted", actor=user, resource_type="attempt", resource_id=attempt_id, details={"score": submitted.get("score"), "max_score": submitted.get("max_score")}, request=request)
        return {**_format_attempt(submitted, responses=repo.get_attempt_responses(attempt_id)), "report": report}

    @app.get("/exams/{exam_id}/attendance")
    def exam_attendance(exam_id: str, user: dict = Depends(_require_roles("instructor", "admin"))):
        _require_exam_management_access(exam_id, user)
        rows = _repo().exam_attendance(exam_id)
        return [
            {
                **row,
                "started_at": _iso(row.get("started_at")) if row.get("started_at") else None,
                "submitted_at": _iso(row.get("submitted_at")) if row.get("submitted_at") else None,
                "attempt_status": row.get("attempt_status") or "not_started",
                "risk_score": min(int(row.get("risk_score") or 0), 100),
            }
            for row in rows
        ]

    @app.get("/exams/{exam_id}/attempts")
    def exam_attempts(exam_id: str, user: dict = Depends(_require_roles("instructor", "admin"))):
        _require_exam_management_access(exam_id, user)
        repo = _repo()
        questions = [_format_question(q, include_correct=True) for q in repo.list_exam_questions(exam_id, include_correct=True)]
        return [
            _format_attempt(
                row,
                questions=questions,
                responses=repo.get_attempt_responses(row["attempt_id"]),
                include_response_grading=True,
            )
            for row in repo.list_attempts_for_exam(exam_id)
        ]

    @app.get("/dashboard/instructor")
    def instructor_dashboard(user: dict = Depends(_require_roles("instructor", "admin"))):
        return _repo().dashboard_metrics(_tenant_id(user))

    @app.get("/dashboard/admin")
    def admin_dashboard(user: dict = Depends(_require_roles("admin"))):
        return _repo().dashboard_metrics(_tenant_id(user))

    @app.get("/dashboard/student")
    def student_dashboard(user: dict = Depends(_require_roles("student"))):
        repo = _repo()
        exams = [_format_exam(row) for row in repo.list_exams(user)]
        return {"assigned_exams": len(exams), "exams": exams}

    @app.get("/settings")
    def get_settings(user: dict = Depends(_current_user)):
        return _repo().get_settings(_tenant_id(user))

    @app.put("/settings")
    def update_settings(req: SettingsRequest, request: Request, user: dict = Depends(_require_roles("admin"))):
        values = _repo().save_settings(req.values, user["user_id"], _tenant_id(user))
        _audit("settings.updated", actor=user, resource_type="settings", details={"keys": list(req.values.keys())}, request=request)
        return values

    @app.get("/tenants")
    def list_tenants(user: dict = Depends(_require_roles("admin"))):
        rows = _repo().list_tenants()
        return [{**row, "settings": json.loads(row.get("settings_json") or "{}")} for row in rows]

    @app.post("/tenants")
    def create_tenant(req: TenantRequest, request: Request, user: dict = Depends(_require_roles("admin"))):
        name = (req.name or "").strip()
        slug = (req.slug or "").strip().lower()
        if len(name) < 2:
            _api_error(422, "validation_error", "Institution name is required.")
        if not slug or any(ch for ch in slug if not (ch.isalnum() or ch in "-_")):
            _api_error(422, "validation_error", "Tenant slug may contain only letters, numbers, hyphens, and underscores.")
        tenant = _repo().create_tenant(name, slug, req.plan_name, req.settings)
        _audit("tenant.created", actor=user, resource_type="tenant", resource_id=tenant.get("tenant_id", ""), request=request)
        return {**tenant, "settings": json.loads(tenant.get("settings_json") or "{}")}

    @app.put("/tenants/{tenant_id}")
    def update_tenant(tenant_id: str, req: TenantRequest, request: Request, user: dict = Depends(_require_roles("admin"))):
        tenant = _repo().update_tenant(
            tenant_id,
            {
                "name": req.name.strip(),
                "slug": req.slug.strip().lower(),
                "plan_name": req.plan_name,
                "status": req.status,
                "settings": req.settings,
            },
        )
        if not tenant:
            _api_error(404, "not_found", "Tenant not found.")
        _audit("tenant.updated", actor=user, resource_type="tenant", resource_id=tenant_id, request=request)
        return {**tenant, "settings": json.loads(tenant.get("settings_json") or "{}")}

    @app.get("/audit-logs")
    def audit_logs(limit: int = 100, user: dict = Depends(_require_roles("admin"))):
        rows = _repo().list_audit_logs(_tenant_id(user), limit)
        out = []
        for row in rows:
            details = row.get("details_json") or "{}"
            try:
                details = json.loads(details)
            except Exception:
                details = {}
            out.append({**row, "details": details})
        return out

    def _validate_role(role: str) -> str:
        role = (role or "").strip().lower()
        if role not in {"student", "instructor", "admin"}:
            _api_error(422, "validation_error", "Role must be student, instructor, or admin.")
        return role

    @app.get("/admin/users", response_model=List[UserPublic])
    def admin_list_users(
        tenant_id: Optional[str] = None,
        role: str = "",
        q: str = "",
        limit: int = 200,
        user: dict = Depends(_require_roles("admin")),
    ):
        requested_tenant = tenant_id or ""
        if requested_tenant and not _repo().get_tenant(requested_tenant):
            _api_error(404, "not_found", "Tenant not found.")
        rows = _repo().list_users(
            tenant_id=requested_tenant or None,
            role=_validate_role(role) if role else "",
            query=(q or "").strip(),
            limit=limit,
        )
        return [_public_user(row) for row in rows]

    @app.post("/admin/users", response_model=UserPublic)
    def admin_create_user(req: AdminUserCreateRequest, request: Request, user: dict = Depends(_require_roles("admin"))):
        email = (req.email or "").strip().lower()
        full_name = (req.full_name or "").strip()
        role = _validate_role(req.role)
        tenant_id = req.tenant_id or _tenant_id(user)
        repo = _repo()
        if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
            _api_error(422, "validation_error", "Enter a valid email address.")
        if len(full_name) < 2:
            _api_error(422, "validation_error", "Enter the user's full name.")
        if not repo.get_tenant(tenant_id):
            _api_error(404, "not_found", "Tenant not found.")
        if repo.get_user_by_email(email):
            _api_error(409, "email_exists", "An account with this email already exists.")
        from core.security import hash_password, validate_password
        errors = validate_password(req.password)
        if errors:
            _api_error(422, "validation_error", "Password does not meet requirements.", errors)
        created = repo.create_user(email, full_name, role, hash_password(req.password), tenant_id)
        _audit(
            "admin.user.created",
            actor=user,
            resource_type="user",
            resource_id=created["user_id"],
            details={"email": email, "role": role, "tenant_id": tenant_id},
            request=request,
        )
        return _public_user(created)

    @app.put("/admin/users/{target_user_id}", response_model=UserPublic)
    def admin_update_user(
        target_user_id: str,
        req: AdminUserUpdateRequest,
        request: Request,
        user: dict = Depends(_require_roles("admin")),
    ):
        repo = _repo()
        target = repo.get_user(target_user_id)
        if not target:
            _api_error(404, "not_found", "User not found.")
        changes = req.dict(exclude_unset=True)
        if not changes:
            return _public_user(target)

        if "role" in changes and changes["role"] is not None:
            changes["role"] = _validate_role(changes["role"])
        if "tenant_id" in changes and changes["tenant_id"] is not None and not repo.get_tenant(changes["tenant_id"]):
            _api_error(404, "not_found", "Tenant not found.")
        if "full_name" in changes and changes["full_name"] is not None:
            changes["full_name"] = changes["full_name"].strip()
            if len(changes["full_name"]) < 2:
                _api_error(422, "validation_error", "Enter the user's full name.")

        governance_keys = {"role", "tenant_id", "is_active"}
        if target_user_id == user["user_id"] and governance_keys.intersection(changes):
            _api_error(403, "forbidden", "You cannot change your own role, tenant, or active status.")

        target_is_last_admin = target.get("role") == "admin" and bool(target.get("is_active", True)) and repo.active_admin_count() <= 1
        new_role = changes.get("role", target.get("role"))
        new_active = bool(changes.get("is_active", target.get("is_active", True)))
        if target_is_last_admin and (new_role != "admin" or not new_active):
            _api_error(409, "last_admin", "At least one active admin account must remain.")

        updated = repo.update_user(target_user_id, changes)
        if not updated:
            _api_error(404, "not_found", "User not found.")
        _audit(
            "admin.user.updated",
            actor=user,
            resource_type="user",
            resource_id=target_user_id,
            details={"changes": {k: v for k, v in changes.items() if k != "password"}},
            request=request,
        )
        return _public_user(updated)

    @app.post("/admin/users/{target_user_id}/password")
    def admin_set_user_password(
        target_user_id: str,
        req: AdminPasswordRequest,
        request: Request,
        user: dict = Depends(_require_roles("admin")),
    ):
        repo = _repo()
        target = repo.get_user(target_user_id)
        if not target:
            _api_error(404, "not_found", "User not found.")
        from core.security import hash_password, validate_password
        errors = validate_password(req.password)
        if errors:
            _api_error(422, "validation_error", "Password does not meet requirements.", errors)
        repo.update_password(target_user_id, hash_password(req.password))
        _audit(
            "admin.user.password_set",
            actor=user,
            resource_type="user",
            resource_id=target_user_id,
            details={"email": target.get("email")},
            request=request,
        )
        return {"status": "ok", "user_id": target_user_id}

    # ── Bridge helper ──────────────────────────────────────────
    def _get_detector():
        """Lazily import the TabSwitchDetector singleton for bridging."""
        try:
            from monitoring.tab_switch_detector import _GLOBAL_DETECTOR
            return _GLOBAL_DETECTOR
        except Exception:
            return None

    def _iso(value: Any) -> str:
        if isinstance(value, datetime):
            normalized = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
            return normalized.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        if value is None:
            return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        return str(value)

    def _normalize_event(row: dict, session_id: str = "") -> dict:
        return {
            "event_id": row.get("event_id") or row.get("EventID") or row.get("id"),
            "session_id": row.get("session_id") or row.get("SessionID") or session_id,
            "student_id": row.get("student_id") or row.get("StudentID") or "",
            "event_type": row.get("event_type") or row.get("EventType") or "",
            "event_time": _iso(row.get("event_time") or row.get("EventTime") or row.get("timestamp")),
            "risk_points": int(row.get("risk_points") or row.get("RiskPoints") or 0),
            "confidence": row.get("confidence"),
            "model_name": row.get("model_name") or "",
            "detection_class": row.get("detection_class") or "",
            "bounding_box_json": row.get("bounding_box_json") or "",
            "evidence_id": row.get("evidence_id") or "",
            "ingest_id": row.get("ingest_id") or "",
            "notes": row.get("notes") or row.get("Notes") or "",
        }

    def _fallback_session_events(session_id: str) -> list[dict]:
        return [
            _normalize_event(e, session_id)
            for e in _events
            if e.get("session_id") == session_id
        ]

    def _fallback_session_summary(session_id: str = "") -> Optional[dict]:
        active_session = _active_session_id()
        requested_session = session_id or active_session
        meta = _session_store.get(requested_session, {})
        has_events = bool(requested_session and _fallback_session_events(requested_session))
        if requested_session and (meta or requested_session == active_session or has_events):
            review = _session_reviews.get(requested_session, {})
            events = _fallback_session_events(requested_session)
            first_event = events[0] if events else {}
            return {
                "session_id": requested_session,
                "user_id": str(meta.get("user_id") or ""),
                "exam_id": str(meta.get("exam_id") or ""),
                "student_id": str(meta.get("student_id") or first_event.get("student_id") or ""),
                "exam_code": str(meta.get("exam_code") or ""),
                "start_time": meta.get("started_at") or meta.get("start_time") or first_event.get("event_time"),
                "end_time": None,
                "status": "Active" if requested_session == active_session else "Offline",
                "final_score": min(sum(e.get("risk_points", 0) for e in events), 100) if events else None,
                "review_mark": review.get("review_mark"),
                "instructor_notes": review.get("instructor_notes"),
            }
        return None

    def _fallback_sessions() -> list[dict]:
        seen = set()
        sessions = []
        for session_id in _session_store:
            summary = _fallback_session_summary(session_id)
            if summary:
                sessions.append(summary)
                seen.add(session_id)
        for event in _events:
            session_id = event.get("session_id")
            if not session_id or session_id in seen:
                continue
            summary = _fallback_session_summary(session_id)
            if summary:
                sessions.append(summary)
                seen.add(session_id)
        sessions.sort(key=lambda row: row.get("start_time") or "", reverse=True)
        return sessions

    def _ensure_fallback_session(session_id: str, student_id: str = "", exam_code: str = ""):
        if not session_id:
            return
        existing = _session_store.get(session_id, {})
        if not existing:
            _session_store[session_id] = {
                "session_id": session_id,
                "student_id": student_id,
                "student_name": student_id,
                "exam_code": exam_code,
                "started_at": datetime.now().isoformat(),
            }
            return
        if student_id and not existing.get("student_id"):
            existing["student_id"] = student_id
        if exam_code and not existing.get("exam_code"):
            existing["exam_code"] = exam_code

    def _browser_log_for_report(session_id: str) -> list[dict]:
        rows = _browser_activity_for_session(session_id)
        return [
            {
                "time": row.get("time") or "",
                "event_type": row.get("type") or "browser",
                "description": row.get("title") or row.get("url") or row.get("category") or "",
                "url": row.get("url") or "",
                "risk": row.get("risk") or "low",
            }
            for row in rows
        ]

    def _get_session_events(session_id: str) -> list[dict]:
        db = _get_db()
        if db and db.is_active:
            try:
                rows = db.query(
                    "SELECT event_id, session_id, student_id, event_type, event_time, risk_points, "
                    "confidence, model_name, detection_class, bounding_box_json, evidence_id, ingest_id, notes "
                    "FROM Events WHERE session_id = ? ORDER BY event_time ASC",
                    (session_id,)
                )
                return [_normalize_event(row, session_id) for row in rows]
            except Exception:
                pass
        return _fallback_session_events(session_id)

    def _browser_risk_label(points: int) -> str:
        if points >= 12:
            return "high"
        if points > 0:
            return "medium"
        return "low"

    def _normalize_browser_activity(row: dict) -> dict:
        timestamp = _iso(row.get("event_time") or row.get("timestamp"))
        points = int(row.get("risk_points") or row.get("risk_impact") or 0)
        return {
            "activity_id": row.get("activity_id"),
            "session_id": str(row.get("session_id") or ""),
            "type": str(row.get("activity_type") or row.get("type") or "browser"),
            "url": str(row.get("url") or ""),
            "title": str(row.get("title") or ""),
            "category": str(row.get("category") or "Unknown"),
            "risk": str(row.get("risk_level") or row.get("risk") or _browser_risk_label(points)),
            "risk_points": points,
            "risk_impact": points,
            "source": str(row.get("source") or ""),
            "ingest_id": str(row.get("ingest_id") or ""),
            "time": timestamp[11:19] if len(timestamp) >= 19 else timestamp,
            "timestamp": timestamp,
        }

    def _browser_activity_from_event(row: dict) -> Optional[dict]:
        event_type = row.get("event_type", "")
        notes = row.get("notes", "")
        points = int(row.get("risk_points") or 0)
        timestamp = row.get("event_time") or row.get("timestamp") or datetime.now().isoformat()
        lower_notes = notes.lower()

        if event_type == "Tab Switch":
            activity_type, category, title = "tab_switch", "Tab", notes or "Left exam tab"
        elif event_type == "Keyboard Shortcut":
            activity_type, category, title = "keyboard", "Keyboard", notes or "Keyboard shortcut"
        elif event_type == "Clipboard Access":
            activity_type = "paste" if "paste" in lower_notes else "copy"
            category, title = "Clipboard", notes or "Clipboard access"
        elif event_type == "DevTools Opened":
            activity_type, category, title = "devtools", "DevTools", notes or "DevTools opened"
        elif event_type == "Fullscreen Exit":
            activity_type, category, title = "fullscreen_exit", "Fullscreen", notes or "Exited fullscreen"
        elif event_type == "Browser Activity":
            activity_type, category, title = "browser", "Browser", notes or "Browser activity"
        else:
            return None

        return {
            "session_id": row.get("session_id", ""),
            "type": activity_type,
            "url": "",
            "title": title,
            "category": category,
            "risk": _browser_risk_label(points),
            "risk_points": points,
            "risk_impact": points,
            "time": str(timestamp)[11:19] if len(str(timestamp)) >= 19 else str(timestamp),
            "timestamp": timestamp,
        }

    def _timestamp_seconds(value: Any) -> Optional[float]:
        try:
            text = str(value or "")
            if not text:
                return None
            return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
        except Exception:
            return None

    def _has_near_browser_row(rows: list[dict], candidate: dict) -> bool:
        candidate_ts = _timestamp_seconds(candidate.get("timestamp"))
        for row in rows:
            if row.get("type") != candidate.get("type"):
                continue
            row_ts = _timestamp_seconds(row.get("timestamp"))
            if candidate_ts is not None and row_ts is not None:
                if abs(candidate_ts - row_ts) <= 2:
                    return True
                continue
            if row.get("title") == candidate.get("title") and row.get("url") == candidate.get("url"):
                return True
        return False

    def _browser_activity_for_session(session_id: str) -> list[dict]:
        rows: list[dict] = []
        db = _get_db()
        if db and db.is_active:
            try:
                from database.student_repository import StudentRepository

                rows = [
                    _normalize_browser_activity(row)
                    for row in StudentRepository(db).get_browser_activity(session_id)
                ]
            except Exception as exc:
                log_event(
                    _api_logger,
                    "browser_activity.read_failed",
                    level="warning",
                    session_id=session_id,
                    error=exc.__class__.__name__,
                )
        for event in _browser_events:
            if event.get("session_id") != session_id or _has_near_browser_row(rows, event):
                continue
            rows.append(event)
        for event in _get_session_events(session_id):
            row = _browser_activity_from_event(event)
            if not row:
                continue
            if _has_near_browser_row(rows, row):
                continue
            rows.append(row)
        rows.sort(key=lambda row: row.get("timestamp") or row.get("time") or "")
        return rows

    def _risk_level(score: int) -> str:
        if score < 20:
            return "Low"
        if score < 50:
            return "Medium"
        if score < 80:
            return "High"
        return "Critical"

    def _active_session_id() -> str:
        return str(_session_meta.get("session_id") or "")

    def _clear_active_session(session_id: str = "") -> None:
        if not session_id or _active_session_id() == session_id:
            _session_meta.clear()

    def _browser_risk_points(risk: str) -> int:
        risk_l = (risk or "").lower()
        if risk_l == "high":
            return 10
        if risk_l == "medium":
            return 5
        return 0

    def _base_points(event_type: str, fallback: int = 0) -> int:
        try:
            from core.risk.risk_config import BASE_POINTS
            return int(BASE_POINTS.get(event_type, fallback))
        except Exception:
            return fallback

    def _active_student_id(session_id: str = "") -> str:
        active = _active_session_id()
        meta = _session_store.get(session_id or active, {})
        return str(meta.get("student_id") or _session_meta.get("student_id") or "")

    def _ingest_key(session_id: str, ingest_id: str, purpose: str) -> str:
        client_key = (ingest_id or uuid.uuid4().hex).strip()
        return hashlib.sha256(f"{session_id}:{purpose}:{client_key}".encode("utf-8")).hexdigest()

    def _persist_event(
        session_id: str,
        student_id: str,
        event_type: str,
        risk_points: int,
        notes: str,
        metadata: dict | None = None,
    ) -> dict:
        metadata = metadata or {}
        if not session_id:
            _api_error(422, "session_required", "A session ID is required for event persistence.")
        ingest_id = _ingest_key(session_id, str(metadata.get("ingest_id") or ""), "risk_event")
        event_time = datetime.now(timezone.utc)
        record = {
            "session_id": session_id,
            "student_id": student_id,
            "event_type": event_type,
            "risk_points": int(risk_points or 0),
            "confidence": metadata.get("confidence"),
            "model_name": metadata.get("model_name") or "",
            "detection_class": metadata.get("detection_class") or "",
            "bounding_box_json": json.dumps(metadata.get("bounding_box") or metadata.get("bounding_box_json") or {}),
            "evidence_id": metadata.get("evidence_id") or "",
            "ingest_id": ingest_id,
            "notes": notes,
            "time": event_time.strftime("%H:%M:%S"),
            "timestamp": event_time.isoformat().replace("+00:00", "Z"),
            "event_time": event_time.isoformat().replace("+00:00", "Z"),
            "persistence": "persisted",
            "duplicate": False,
        }
        db = _get_db()
        if not db or not db.is_active:
            _api_error(503, "database_unavailable", "Event persistence is unavailable. Retry the event.")
        from database.student_repository import StudentRepository

        repo = StudentRepository(db)
        try:
            if repo.event_ingest_exists(ingest_id):
                return {**record, "duplicate": True}
            repo.upsert_session(session_id, student_id=student_id, status="Active")
            repo.insert_event(
                session_id,
                student_id,
                event_type,
                event_time,
                int(risk_points or 0),
                notes,
                confidence=metadata.get("confidence"),
                model_name=str(metadata.get("model_name") or ""),
                detection_class=str(metadata.get("detection_class") or ""),
                bounding_box_json=json.dumps(metadata.get("bounding_box") or metadata.get("bounding_box_json") or {}),
                evidence_id=str(metadata.get("evidence_id") or ""),
                ingest_id=ingest_id,
            )
        except Exception as exc:
            try:
                duplicate = repo.event_ingest_exists(ingest_id)
            except Exception:
                duplicate = False
            if duplicate:
                return {**record, "duplicate": True}
            log_event(
                _api_logger,
                "event.persist_failed",
                level="error",
                session_id=session_id,
                event_type=event_type,
                error=exc.__class__.__name__,
            )
            _api_error(503, "event_not_persisted", "The proctor event could not be persisted. Retry the event.")
        _ensure_fallback_session(session_id, student_id)
        _events.append(record)
        return record

    def _record_browser_activity(
        event_type: str,
        *,
        session_id: str = "",
        url: str = "",
        title: str = "",
        category: str = "Unknown",
        risk: str = "low",
        source: str = "browser_client",
        ingest_id: str = "",
    ) -> dict:
        risk_points = _browser_risk_points(risk)
        event_time = datetime.now(timezone.utc)
        resolved_session_id = session_id or _active_session_id()
        resolved_ingest_id = _ingest_key(resolved_session_id, ingest_id, "browser_activity")
        record = {
            "session_id": resolved_session_id,
            "type": event_type,
            "url": url,
            "title": title,
            "category": category,
            "risk": risk,
            "risk_points": risk_points,
            "risk_impact": risk_points,
            "source": source,
            "ingest_id": resolved_ingest_id,
            "time": event_time.strftime("%H:%M:%S"),
            "timestamp": event_time.isoformat().replace("+00:00", "Z"),
            "persistence": "persisted",
            "duplicate": False,
        }
        if not resolved_session_id:
            _api_error(422, "session_required", "A session ID is required for browser activity.")
        db = _get_db()
        if not db or not db.is_active:
            _api_error(503, "database_unavailable", "Browser activity persistence is unavailable. Retry the event.")
        from database.student_repository import StudentRepository

        repo = StudentRepository(db)
        try:
            if repo.browser_activity_ingest_exists(resolved_ingest_id):
                return {**record, "duplicate": True}
            repo.insert_browser_activity(
                resolved_session_id,
                event_type,
                event_time,
                url=url,
                title=title,
                category=category,
                risk_level=risk,
                risk_points=risk_points,
                source=source,
                ingest_id=resolved_ingest_id,
            )
        except Exception as exc:
            try:
                duplicate = repo.browser_activity_ingest_exists(resolved_ingest_id)
            except Exception:
                duplicate = False
            if duplicate:
                return {**record, "duplicate": True}
            log_event(
                _api_logger,
                "browser_activity.persist_failed",
                level="error",
                session_id=resolved_session_id,
                activity_type=event_type,
                error=exc.__class__.__name__,
            )
            _api_error(503, "browser_activity_not_persisted", "Browser activity could not be persisted. Retry the event.")
        _browser_events.append(record)
        return record

    def _record_browser_risk_event(
        session_id: str,
        event_type: str,
        canonical_event: str,
        notes: str,
        risk: str = "low",
        ingest_id: str = "",
    ) -> dict | None:
        sid = session_id or _active_session_id()
        if not sid:
            return None
        points = _base_points(canonical_event, _browser_risk_points(risk))
        return _persist_event(
            sid,
            _active_student_id(sid),
            canonical_event,
            points,
            notes,
            {"ingest_id": ingest_id},
        )

    def _write_active_proctor_state(running: bool, session_id: str = "", student_id: str = "", exam_code: str = ""):
        from config.settings import PROCTOR_ACTIVE_FILE

        path = Path(PROCTOR_ACTIVE_FILE)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({
                "running": running,
                "session_id": session_id,
                "student_id": student_id,
                "exam_code": exam_code,
                "updated_at": datetime.now().isoformat(),
            }, indent=2),
            encoding="utf-8",
        )

    def _read_engine_status() -> dict:
        from config.settings import PROCTOR_POLL_SEC, PROCTOR_STATUS_FILE

        path = Path(PROCTOR_STATUS_FILE)
        if not path.exists():
            return {
                "engine_running": False,
                "ready": False,
                "status": "stopped",
                "primary_camera": {"active": False},
                "secondary_camera": {"active": False},
                "microphone": {"active": False},
                "video_stream": {"active": False},
                "phone_detection": {"available": False, "status": "unavailable", "reason": "engine not running"},
            }
        try:
            status = json.loads(path.read_text(encoding="utf-8"))
            updated_at = status.get("updated_at")
            stale_after = max(5.0, float(PROCTOR_POLL_SEC) * 6)
            try:
                stale = not updated_at or (
                    datetime.now(timezone.utc) - _parse_dt(updated_at)
                ).total_seconds() > stale_after
            except Exception:
                stale = True
            if stale:
                status.update({
                    "engine_running": False,
                    "ready": False,
                    "status": "stopped",
                    "last_error": "Proctor engine status heartbeat is stale.",
                })
                status["primary_camera"] = {**(status.get("primary_camera") or {}), "active": False}
                status["secondary_camera"] = {**(status.get("secondary_camera") or {}), "active": False}
                status["microphone"] = {**(status.get("microphone") or {}), "active": False, "level": 0.0}
                status["video_stream"] = {**(status.get("video_stream") or {}), "active": False}
            return status
        except Exception as exc:
            return {"engine_running": False, "ready": False, "status": "stopped", "last_error": str(exc)}

    # ── Browser Guard (extension → FastAPI → bridge) ─────────

    def _browser_event_should_score(event_type: str) -> bool:
        return (event_type or "").strip().lower() not in {"heartbeat", "ping", "window_focus"}

    def _handle_browser_guard_event(ev: BrowserGuardEvent, principal: dict) -> dict:
        global _guard_last_seen
        session_id = _authorized_browser_session(ev.session_id or "", principal)
        trusted_guard = principal.get("kind") in {"browser_guard", "device"}
        if trusted_guard and ev.source in {"extension", "browser_guard_extension", "browser_guard_companion"}:
            _guard_last_seen = time.monotonic()
        if not _browser_event_should_score(ev.type):
            return {"status": "ok", "total": len(_browser_events), "scored": False, "persistence": "not_applicable"}
        record = _record_browser_activity(
            ev.type,
            session_id=session_id,
            url=ev.url,
            title=ev.title,
            category=ev.category,
            risk=ev.risk,
            source=ev.source,
            ingest_id=ev.ingest_id,
        )
        from core.events.event_types import EVENT_BROWSER_ACTIVITY, EVENT_TAB_SWITCH

        canonical = EVENT_TAB_SWITCH if ev.type == "tab_switch" else EVENT_BROWSER_ACTIVITY
        risk_record = _record_browser_risk_event(
            session_id,
            ev.type,
            canonical,
            f"{ev.type}: {ev.title or ev.url or ev.category}",
            risk=ev.risk,
            ingest_id=ev.ingest_id,
        )
        det = _get_detector()
        if det:
            det.bridge_browser_guard_event(ev.type, ev.url, ev.title, ev.category, ev.risk)
        return {
            "status": "ok",
            "total": len(_browser_events),
            "scored": True,
            "persistence": "persisted",
            "duplicate": bool(record.get("duplicate") and (risk_record or {}).get("duplicate")),
        }

    @app.post("/browser-guard/token")
    def create_browser_guard_session_token(
        req: BrowserGuardTokenRequest,
        user: dict = Depends(_require_roles("student")),
    ):
        _require_session_access(req.session_id, user)
        if req.session_id != _active_session_id():
            _api_error(409, "session_not_active", "Browser Guard tokens are issued only for the active session.")
        from core.security import create_browser_guard_token

        return {"token": create_browser_guard_token(user, req.session_id), "session_id": req.session_id}

    @app.post("/browser-events")
    def browser_guard_event(ev: BrowserGuardEvent, principal: dict = Depends(_browser_signal_principal)):
        return _handle_browser_guard_event(ev, principal)

    @app.post("/browser-guard/event")
    def browser_guard_event_alias(ev: BrowserGuardEvent, principal: dict = Depends(_browser_signal_principal)):
        """Alias used by the packaged Browser Guard extension."""
        return _handle_browser_guard_event(ev, principal)

    @app.get("/browser-guard/ping")
    def browser_guard_ping(
        source: str = "browser_guard",
        version: str = "",
        principal: dict = Depends(_browser_signal_principal),
    ):
        global _guard_last_seen
        if (
            principal.get("kind") in {"browser_guard", "device"}
            and source in {"extension", "browser_guard_extension", "browser_guard_companion"}
        ):
            _guard_last_seen = time.monotonic()
        det = _get_detector()
        if det:
            det.bridge_browser_guard_event("ping", "", "", "", "low")
        return {"status": "alive", "mode": "guard", "source": source, "version": version}

    @app.get("/browser-guard/active")
    def guard_active(_user: dict = Depends(_current_user)):
        active = _guard_last_seen > 0 and (time.monotonic() - _guard_last_seen) <= 45
        return {
            "active": active,
            "last_seen_seconds_ago": round(time.monotonic() - _guard_last_seen, 1) if _guard_last_seen else None,
        }

    # ── Extension content.js events (keyboard / clipboard) ───

    class KeyEvent(BaseModel):
        combo: str = "unknown"
        session_id: Optional[str] = None
        ingest_id: str = ""

    class ClipboardEvent(BaseModel):
        action: str = "copy"
        session_id: Optional[str] = None
        ingest_id: str = ""

    @app.post("/keyboard-event")
    def keyboard_event(ev: KeyEvent, principal: dict = Depends(_browser_signal_principal)):
        session_id = _authorized_browser_session(ev.session_id or "", principal)
        record = _record_browser_activity(
            "keyboard",
            session_id=session_id,
            title=f"Shortcut: {ev.combo}",
            category="Keyboard",
            risk="medium",
            ingest_id=ev.ingest_id,
        )
        from core.events.event_types import EVENT_KEYBOARD_SHORTCUT
        risk_record = _record_browser_risk_event(
            record.get("session_id", ""),
            "keyboard",
            EVENT_KEYBOARD_SHORTCUT,
            f"Keyboard shortcut: {ev.combo}",
            risk="medium",
            ingest_id=ev.ingest_id,
        )
        det = _get_detector()
        if det:
            det.bridge_extension_key_event(ev.combo)
        return {"status": "ok", "persistence": "persisted", "duplicate": bool(record.get("duplicate") and (risk_record or {}).get("duplicate"))}

    @app.post("/key-event")
    def key_event_alias(ev: KeyEvent, principal: dict = Depends(_browser_signal_principal)):
        """Alias for backward compatibility."""
        return keyboard_event(ev, principal)

    @app.post("/clipboard-event")
    def clipboard_event(ev: ClipboardEvent, principal: dict = Depends(_browser_signal_principal)):
        session_id = _authorized_browser_session(ev.session_id or "", principal)
        record = _record_browser_activity(
            ev.action,
            session_id=session_id,
            title=f"Clipboard {ev.action}",
            category="Clipboard",
            risk="medium",
            ingest_id=ev.ingest_id,
        )
        from core.events.event_types import EVENT_CLIPBOARD_ACCESS
        risk_record = _record_browser_risk_event(
            record.get("session_id", ""),
            ev.action,
            EVENT_CLIPBOARD_ACCESS,
            f"Clipboard {ev.action}",
            risk="medium",
            ingest_id=ev.ingest_id,
        )
        det = _get_detector()
        if det:
            det.bridge_extension_clipboard_event(ev.action)
        return {"status": "ok", "persistence": "persisted", "duplicate": bool(record.get("duplicate") and (risk_record or {}).get("duplicate"))}

    class TabEvent(BaseModel):
        direction: str = "away"
        session_id: Optional[str] = None
        ingest_id: str = ""

    class DevToolsEvent(BaseModel):
        state: str = "open"
        session_id: Optional[str] = None
        ingest_id: str = ""

    class FullscreenEvent(BaseModel):
        state: str = "exit"
        session_id: Optional[str] = None
        ingest_id: str = ""

    @app.post("/tab-event")
    def tab_event(ev: TabEvent, principal: dict = Depends(_browser_signal_principal)):
        session_id = _authorized_browser_session(ev.session_id or "", principal)
        if ev.direction == "away":
            record = _record_browser_activity(
                "tab_switch",
                session_id=session_id,
                title="Left exam tab",
                category="Tab",
                risk="medium",
                ingest_id=ev.ingest_id,
            )
            from core.events.event_types import EVENT_TAB_SWITCH
            risk_record = _record_browser_risk_event(
                record.get("session_id", ""),
                "tab_switch",
                EVENT_TAB_SWITCH,
                "Left exam tab or browser window lost focus",
                risk="medium",
                ingest_id=ev.ingest_id,
            )
        else:
            record = None
            risk_record = None
        det = _get_detector()
        if det:
            det.bridge_tab_event(ev.direction)
        return {
            "status": "ok",
            "persistence": "persisted" if record else "not_applicable",
            "duplicate": bool(record and record.get("duplicate") and (risk_record or {}).get("duplicate")),
        }

    @app.post("/devtools-event")
    def devtools_event(ev: DevToolsEvent, principal: dict = Depends(_browser_signal_principal)):
        session_id = _authorized_browser_session(ev.session_id or "", principal)
        if ev.state == "open":
            record = _record_browser_activity(
                "devtools",
                session_id=session_id,
                title="DevTools opened",
                category="DevTools",
                risk="high",
                ingest_id=ev.ingest_id,
            )
            from core.events.event_types import EVENT_DEVTOOLS_OPENED
            risk_record = _record_browser_risk_event(
                record.get("session_id", ""),
                "devtools",
                EVENT_DEVTOOLS_OPENED,
                "DevTools opened",
                risk="high",
                ingest_id=ev.ingest_id,
            )
        else:
            record = None
            risk_record = None
        det = _get_detector()
        if det:
            det.bridge_devtools_event(ev.state)
        return {
            "status": "ok",
            "persistence": "persisted" if record else "not_applicable",
            "duplicate": bool(record and record.get("duplicate") and (risk_record or {}).get("duplicate")),
        }

    @app.post("/fullscreen-event")
    def fullscreen_event(ev: FullscreenEvent, principal: dict = Depends(_browser_signal_principal)):
        session_id = _authorized_browser_session(ev.session_id or "", principal)
        normalized_state = "exit" if ev.state in {"exit", "exited"} else ev.state
        if normalized_state == "exit":
            record = _record_browser_activity(
                "fullscreen_exit",
                session_id=session_id,
                title="Exited fullscreen",
                category="Fullscreen",
                risk="medium",
                ingest_id=ev.ingest_id,
            )
            from core.events.event_types import EVENT_FULLSCREEN_EXIT
            risk_record = _record_browser_risk_event(
                record.get("session_id", ""),
                "fullscreen_exit",
                EVENT_FULLSCREEN_EXIT,
                "Exited fullscreen mode",
                risk="medium",
                ingest_id=ev.ingest_id,
            )
        else:
            record = None
            risk_record = None
        det = _get_detector()
        if det:
            det.bridge_fullscreen_event(normalized_state)
        return {
            "status": "ok",
            "persistence": "persisted" if record else "not_applicable",
            "duplicate": bool(record and record.get("duplicate") and (risk_record or {}).get("duplicate")),
        }

    # ── Proctor Events ────────────────────────────────────────

    @app.post("/events")
    def post_event(ev: ProctorEvent, _device: dict = Depends(_require_proctor_device)):
        active_session_id = _active_session_id()
        if not active_session_id or ev.session_id != active_session_id:
            _api_error(409, "session_not_active", "Proctor events are accepted only for the active session.")
        record = _persist_event(
            ev.session_id,
            _active_student_id(ev.session_id),
            ev.event_type,
            _base_points(ev.event_type, ev.risk_points),
            ev.notes,
            {
                "confidence": ev.confidence,
                "model_name": ev.model_name,
                "detection_class": ev.detection_class,
                "bounding_box": ev.bounding_box,
                "evidence_id": ev.evidence_id,
                "ingest_id": ev.ingest_id,
            },
        )
        return {
            "status": "ok",
            "total": len(_events),
            "persistence": record.get("persistence"),
            "duplicate": bool(record.get("duplicate")),
        }

    # ── Session ───────────────────────────────────────────────

    @app.post("/sessions/start")
    def start_session(meta: SessionMeta, request: Request, user: dict = Depends(_current_user)):
        from core.security import new_id
        session_id = meta.session_id or new_id("session")
        meta_data = meta.model_dump()
        meta_data["session_id"] = session_id
        if user["role"] == "student" and meta.exam_id:
            repo = _repo()
            if not repo.exam_assigned_to_student(meta.exam_id, user["user_id"]):
                _api_error(403, "forbidden", "This exam is not assigned to you.")
        db = _get_db()
        if not db or not db.is_active:
            _api_error(503, "database_unavailable", "Session persistence is unavailable. Retry session start.")
        started_at = datetime.now(timezone.utc)
        try:
            from database.student_repository import StudentRepository

            StudentRepository(db).upsert_session(
                session_id,
                student_id=meta.student_id or user["user_id"],
                student_name=meta.student_name or user.get("full_name", ""),
                exam_code=meta.exam_code or meta.exam_id,
                user_id=user["user_id"],
                exam_id=meta.exam_id,
                roll_number=meta.roll_number,
                tenant_id=_tenant_id(user),
                start_time=started_at,
                status="Active",
            )
        except Exception as exc:
            log_event(
                _api_logger,
                "session.persist_failed",
                level="error",
                session_id=session_id,
                error=exc.__class__.__name__,
            )
            _api_error(503, "session_not_persisted", "The session could not be persisted. Retry session start.")
        _session_meta.update(meta_data)
        _session_meta["user_id"] = user["user_id"]
        _session_meta["started_at"] = started_at.isoformat().replace("+00:00", "Z")
        _session_store[session_id] = {
            **meta_data,
            "user_id": user["user_id"],
            "tenant_id": _tenant_id(user),
            "status": "Active",
            "started_at": _session_meta["started_at"],
        }
        _write_active_proctor_state(True, session_id, meta.student_id or user["user_id"], meta.exam_code)
        _audit(
            "session.started",
            actor=user,
            resource_type="session",
            resource_id=session_id,
            details={"exam_id": meta.exam_id, "exam_code": meta.exam_code},
            request=request,
        )
        return {"status": "ok", "session_id": session_id, "persistence": "persisted"}

    @app.post("/sessions/{session_id}/end")
    def end_session(session_id: str, req: SessionEndRequest, request: Request, user: dict = Depends(_current_user)):
        _require_session_access(session_id, user)
        repo = _repo()
        repo.end_session(session_id)
        if _active_session_id() == session_id:
            _write_active_proctor_state(False)
            _clear_active_session(session_id)
        report = None
        if req.generate_report:
            try:
                path = _generate_report_file(session_id)
                report = _report_metadata(session_id, path)
            except Exception:
                report = None
        _audit("session.ended", actor=user, resource_type="session", resource_id=session_id, request=request)
        return {"status": "ok", "session_id": session_id, "report": report}

    @app.post("/proctor/start", response_model=ProctorControlResponse)
    def start_proctor(req: ProctorStartRequest, user: dict = Depends(_require_roles("student"))):
        _require_session_access(req.session_id, user)
        session = _session_store.setdefault(
            req.session_id,
            {
                "session_id": req.session_id,
                "user_id": user["user_id"],
                "student_id": user["user_id"],
                "tenant_id": _tenant_id(user),
                "status": "Active",
            },
        )
        _session_meta["session_id"] = req.session_id
        _session_meta["student_id"] = user["user_id"]
        if req.exam_code:
            _session_meta["exam_code"] = req.exam_code
        session["status"] = "Active"
        _write_active_proctor_state(True, req.session_id, user["user_id"], req.exam_code)
        return {"status": "ok", "session_id": req.session_id}

    @app.post("/proctor/stop", response_model=ProctorControlResponse)
    def stop_proctor(user: dict = Depends(_require_roles("student"))):
        sid = _active_session_id()
        if sid:
            _require_session_access(sid, user)
        _write_active_proctor_state(False)
        _clear_active_session(sid)
        return {"status": "ok", "session_id": sid or None}

    @app.get("/proctor/status")
    def proctor_status(user: dict = Depends(_current_user)):
        engine = _read_engine_status()
        db = _get_db()
        guard_active_now = _guard_last_seen > 0 and (time.monotonic() - _guard_last_seen) <= 45
        active_session_id = engine.get("active_session_id") or _active_session_id() or None
        video_access_token = None
        if active_session_id:
            _require_session_access(str(active_session_id), user)
            from core.security import create_media_token
            video_access_token = create_media_token(user, str(active_session_id))
        engine.update({
            "active_session_id": active_session_id,
            "video_access_token": video_access_token,
            "browser_guard": {
                "active": guard_active_now,
                "last_seen_seconds_ago": round(time.monotonic() - _guard_last_seen, 1) if _guard_last_seen else None,
            },
            "backend": {"connected": True},
            "database": {
                "connected": bool(db and db.is_active),
                "offline_fallback": not bool(db and db.is_active),
            },
        })
        return engine

    @app.get("/sessions", response_model=List[SessionSummary])
    def get_sessions(user: dict = Depends(_current_user)):
        db = _get_db()
        if not db or not db.is_active:
            rows = _fallback_sessions()
            if user["role"] == "student":
                rows = [s for s in rows if s.get("user_id") == user["user_id"] or s.get("student_id") == user["user_id"]]
            return rows

        from database.student_repository import StudentRepository
        repo = StudentRepository(db)
        sessions = repo.get_all_sessions()
        if user["role"] == "student":
            sessions = [s for s in sessions if s.get("user_id") == user["user_id"]]
        elif user["role"] == "instructor":
            sessions = [s for s in sessions if (s.get("tenant_id") or "tenant_default") == _tenant_id(user)]

        # Convert datetime to string
        for s in sessions:
            if s.get("start_time"):
                s["start_time"] = str(s["start_time"])
            if s.get("end_time"):
                s["end_time"] = str(s["end_time"])
            if s.get("final_score") is not None:
                s["final_score"] = min(int(s.get("final_score") or 0), 100)
        return sessions

    @app.get("/sessions/{session_id}", response_model=SessionDetail)
    def get_session(session_id: str, user: dict = Depends(_current_user)):
        _require_session_access(session_id, user)
        db = _get_db()
        if not db or not db.is_active:
            s = _fallback_session_summary(session_id)
            if not s:
                raise HTTPException(status_code=404, detail="Session not found")
        else:
            from database.student_repository import StudentRepository
            repo = StudentRepository(db)
            s = repo.get_session(session_id)
            if not s:
                s = _fallback_session_summary(session_id)
            if not s:
                raise HTTPException(status_code=404, detail="Session not found")

        if s.get("start_time"): s["start_time"] = str(s["start_time"])
        if s.get("end_time"): s["end_time"] = str(s["end_time"])
        if s.get("final_score") is not None:
            s["final_score"] = min(int(s.get("final_score") or 0), 100)

        ev = _get_session_events(session_id)
        s["events"] = ev
        s["event_count"] = len(ev)

        return s

    @app.get("/sessions/{session_id}/events", response_model=List[EventItem])
    def get_session_events(session_id: str, user: dict = Depends(_current_user)):
        _require_session_access(session_id, user)
        return _get_session_events(session_id)

    @app.get("/sessions/{session_id}/risk", response_model=RiskResponse)
    def get_risk(session_id: str, user: dict = Depends(_current_user)):
        _require_session_access(session_id, user)
        ev = _get_session_events(session_id)
        total = sum(e.get("risk_points", 0) for e in ev)

        contributors = []
        counts = {}
        for e in ev:
            event_type = e.get("event_type", "")
            counts[event_type] = counts.get(event_type, 0) + e.get("risk_points", 0)

        for k, points in counts.items():
            contributors.append({"event_type": k, "points": min(points, 100)})
        contributors.sort(key=lambda row: row["points"], reverse=True)

        risk_score = min(total, 100)

        return {
            "session_id": session_id,
            "risk_score": risk_score,
            "risk_level": _risk_level(risk_score),
            "contributors": contributors
        }

    @app.get("/sessions/{session_id}/evidence", response_model=List[EvidenceItem])
    def get_evidence(session_id: str, user: dict = Depends(_current_user)):
        _require_session_access(session_id, user)
        from config.settings import SCREENSHOTS_DIR

        def capture_url(path: str) -> str:
            rel = os.path.relpath(path, SCREENSHOTS_DIR).replace("\\", "/")
            return f"/captures/{quote(rel, safe='/')}?session_id={quote(session_id, safe='')}"

        evidence = []
        session_dir = os.path.join(SCREENSHOTS_DIR, session_id)
        index_path = os.path.join(session_dir, "evidence_index.json")

        if os.path.exists(index_path):
            try:
                with open(index_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for item in data.get("evidence", []):
                    path = item.get("path") or os.path.join(session_dir, item.get("filename", ""))
                    if not path or not os.path.exists(path):
                        continue
                    evidence.append({
                        "session_id": item.get("session_id") or session_id,
                        "filename": item.get("filename") or os.path.basename(path),
                        "event_type": item.get("event_type") or "screenshot",
                        "timestamp": item.get("timestamp") or datetime.fromtimestamp(os.path.getmtime(path)).isoformat(),
                        "filepath": capture_url(path),
                        "risk_points": item.get("risk_score"),
                        "camera": item.get("camera"),
                    })
                return evidence
            except Exception:
                evidence = []

        if os.path.exists(SCREENSHOTS_DIR):
            for root, _, files in os.walk(SCREENSHOTS_DIR):
                parent = os.path.basename(root)
                for file in files:
                    if not file.lower().endswith((".jpg", ".jpeg", ".png")):
                        continue
                    if parent != session_id and not file.startswith(session_id):
                        continue
                    path = os.path.join(root, file)
                    event_type = "screenshot"
                    parts = os.path.splitext(file)[0].split("_")
                    if len(parts) > 3:
                        event_type = " ".join(parts[3:-1] or ["screenshot"]).replace("-", " ")
                    evidence.append({
                        "session_id": session_id,
                        "filename": file,
                        "event_type": event_type,
                        "timestamp": datetime.fromtimestamp(os.path.getmtime(path)).isoformat(),
                        "filepath": capture_url(path),
                    })
        return evidence

    def _resolve_session_capture(capture_path: str, session_id: str) -> Path:
        from config.settings import SCREENSHOTS_DIR

        base = Path(SCREENSHOTS_DIR).resolve()
        candidate = (base / capture_path).resolve()
        try:
            relative = candidate.relative_to(base)
        except ValueError as exc:
            raise ValueError("Capture path escapes the evidence directory") from exc
        belongs_to_session = (
            bool(relative.parts and relative.parts[0] == session_id)
            or candidate.name.startswith(f"{session_id}_")
        )
        if not belongs_to_session:
            raise ValueError("Capture does not belong to the requested session")
        return candidate

    @app.get("/captures/{capture_path:path}")
    def download_capture(capture_path: str, session_id: str, user: dict = Depends(_current_user)):
        _require_session_access(session_id, user)
        try:
            path = _resolve_session_capture(capture_path, session_id)
        except ValueError:
            _api_error(404, "capture_not_found", "Evidence capture was not found.")
        if not path.is_file():
            _api_error(404, "capture_not_found", "Evidence capture was not found.")
        response = FileResponse(path=path, filename=path.name)
        response.headers["Cache-Control"] = "private, no-store"
        return response

    @app.post("/evidence")
    def create_evidence(req: EvidenceCaptureRequest, request: Request, user: dict = Depends(_current_user)):
        _require_session_access(req.session_id, user)
        from config.settings import SCREENSHOTS_DIR
        session_dir = Path(SCREENSHOTS_DIR) / req.session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        filepath = req.filepath
        if req.image_data:
            import base64
            payload = req.image_data.split(",", 1)[-1]
            data = base64.b64decode(payload)
            filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}_{req.evidence_type}.jpg"
            path = session_dir / filename
            path.write_bytes(data)
            filepath = str(path)
        if not filepath:
            _api_error(422, "validation_error", "Evidence image data or filepath is required.")
        evidence = _repo().insert_evidence(
            req.session_id,
            user["user_id"],
            req.evidence_type,
            req.label or req.evidence_type,
            filepath,
            _tenant_id(user),
            {
                "confidence": req.confidence,
                "model_name": req.model_name,
                "detection_class": req.detection_class,
                "bounding_box": req.bounding_box or {},
            },
        )
        _audit(
            "evidence.created",
            actor=user,
            resource_type="evidence",
            resource_id=evidence["evidence_id"],
            details={"session_id": req.session_id, "type": req.evidence_type},
            request=request,
        )
        return evidence

    @app.get("/sessions/{session_id}/browser-activity", response_model=List[BrowserActivityItem])
    def get_browser_activity(session_id: str, user: dict = Depends(_current_user)):
        _require_session_access(session_id, user)
        return _browser_activity_for_session(session_id)

    @app.get("/sessions/{session_id}/report", response_model=ReportMetadata)
    def get_report(session_id: str, user: dict = Depends(_current_user)):
        _require_session_access(session_id, user)
        from config.settings import REPORTS_DIR
        pdf_path = os.path.join(REPORTS_DIR, f"{session_id}_report.pdf")
        if os.path.exists(pdf_path):
            return _report_metadata(session_id, pdf_path)
        raise HTTPException(status_code=404, detail="Report not generated")

    @app.get("/sessions/{session_id}/report/download")
    def download_report(session_id: str, user: dict = Depends(_current_user)):
        _require_session_access(session_id, user)
        from config.settings import REPORTS_DIR
        pdf_path = os.path.join(REPORTS_DIR, f"{session_id}_report.pdf")
        if os.path.exists(pdf_path):
            return FileResponse(path=pdf_path, filename=f"{session_id}_report.pdf", media_type='application/pdf')
        raise HTTPException(status_code=404, detail="Report not found")

    def _generate_report_file(session_id: str) -> str:
        from core.reporting.pdf_generator import PDFReportGenerator
        db = _get_db()
        from database.student_repository import StudentRepository
        repo = StudentRepository(db) if db and db.is_active else None

        session = None if repo else _fallback_session_summary(session_id)
        events = None if repo else _get_session_events(session_id)
        browser_log = None if repo else _browser_log_for_report(session_id)
        gen = PDFReportGenerator(
            session_id,
            repo=repo,
            session=session,
            events=events,
            browser_log=browser_log,
        )
        path = gen.generate()
        if not path:
            raise RuntimeError("Report generation failed")
        return path

    def _report_metadata(session_id: str, pdf_path: str) -> dict:
        risk_score = min(sum(int(row.get("risk_points") or 0) for row in _get_session_events(session_id)), 100)
        risk_level = _risk_level(risk_score).lower()
        generated_at = datetime.fromtimestamp(os.path.getmtime(pdf_path), timezone.utc).isoformat().replace("+00:00", "Z")
        return {
            "session_id": session_id,
            "status": "ready",
            "risk_score": risk_score,
            "risk_level": risk_level,
            "generated_at": generated_at,
            "pdf_url": f"/sessions/{quote(session_id, safe='')}/report/download",
            "summary": f"{risk_level.title()} risk ({risk_score}/100). Manual review is required before any academic decision.",
        }

    @app.post("/reports/generate", response_model=ReportMetadata)
    def generate_report(req: GenerateReportRequest, request: Request, user: dict = Depends(_require_roles("instructor", "admin"))):
        _require_session_access(req.session_id, user)
        path = _generate_report_file(req.session_id)
        if path:
            _audit("report.generated", actor=user, resource_type="session", resource_id=req.session_id, request=request)
            return _report_metadata(req.session_id, path)
        raise HTTPException(status_code=500, detail="Report generation failed")

    @app.post("/sessions/{session_id}/review", response_model=ReviewResponse)
    def submit_review(session_id: str, req: ReviewRequest, request: Request, user: dict = Depends(_require_roles("instructor", "admin"))):
        db = _get_db()
        if not db or not db.is_active:
            _ensure_fallback_session(session_id)
            _session_reviews[session_id] = req.model_dump()
            _audit("session.reviewed", actor=user, resource_type="session", resource_id=session_id, request=request)
            return {"status": "ok", "session_id": session_id}

        from database.student_repository import StudentRepository
        repo = StudentRepository(db)
        repo.update_session_review(session_id, req.review_mark, req.instructor_notes)
        _audit("session.reviewed", actor=user, resource_type="session", resource_id=session_id, request=request)
        return {"status": "ok", "session_id": session_id}

    # ── Assistant ─────────────────────────────────────────────

    class AssistantQuery(BaseModel):
        query: str
        role:  str = "student"
        context: Optional[dict] = None

    class AssistantResponse(BaseModel):
        found: bool
        question: str
        answer: str
        intent: str = ""
        confidence: float = 0.0
        quick_actions: List[str] = []
        references: List[str] = []

    @app.post("/assistant/query", response_model=AssistantResponse)
    def assistant_query(q: AssistantQuery, user: dict = Depends(_current_user)):
        from core.assistant.intent_matcher import chat
        result = chat(q.query, user.get("role") or q.role, context=q.context)
        return {
            "found": bool(result.get("found")),
            "question": q.query,
            "answer": result.get("answer", ""),
            "intent": result.get("intent", ""),
            "confidence": float(result.get("confidence", 0.0)),
            "quick_actions": result.get("quick_actions", []),
            "references": result.get("references", []),
        }

    @app.get("/sessions/{session_id}/risk-trend")
    def get_session_risk_trend(session_id: str, user: dict = Depends(_current_user)):
        _require_session_access(session_id, user)
        events = _get_session_events(session_id)
        if not events:
            return []

        trend = []
        cumulative_score = 0
        for row in events:
            points = row.get("risk_points", 0)
            cumulative_score += points
            trend.append({"timestamp": row["event_time"], "score": min(cumulative_score, 100)})

        return trend

    @app.get("/sessions/{session_id}/audio")
    def get_session_audio_events(session_id: str, user: dict = Depends(_current_user)):
        _require_session_access(session_id, user)
        rows = [
            row for row in _get_session_events(session_id)
            if any(token in row.get("event_type", "").lower()
                   for token in ("audio", "voice", "sound", "noise"))
        ]

        audio_events = []
        for row in rows:
            audio_events.append({
                "id": row.get("event_id") or f"aud_{len(audio_events)}",
                "session_id": row.get("session_id", session_id),
                "timestamp": row.get("event_time", datetime.now().isoformat()),
                "event_type": row.get("event_type", ""),
                "description": row.get("notes", ""),
                "risk_points": row.get("risk_points", 0)
            })

        return audio_events

else:
    # Import-failure fallback used only to report missing backend dependencies.
    app = None


def start_api_server(host: str = "127.0.0.1", port: int = 5051):
    """Start the FastAPI server in a background thread."""
    if not _FASTAPI_AVAILABLE:
        print("[ProctorAI] FastAPI backend skipped: required imports failed.")
        if _FASTAPI_IMPORT_ERROR:
            print(f"  Import error: {_FASTAPI_IMPORT_ERROR}")
        print("  Install with: pip install -r requirements.txt")
        return
    import socket
    import threading
    import uvicorn

    try:
        with socket.create_connection((host, port), timeout=0.5):
            print(f"[ProctorAI] FastAPI backend already running on http://{host}:{port}")
            return
    except OSError:
        pass

    def _run():
        uvicorn.run(app, host=host, port=port,
                    log_level="error", access_log=False)

    t = threading.Thread(target=_run, daemon=True, name="FastAPIServer")
    t.start()
    print(f"[ProctorAI] FastAPI backend running on http://{host}:{port}")
