from __future__ import annotations

from typing import Any, Callable, Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from services.identity_service import IdentityService, IdentityServiceError, OAuthFlowError


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


def create_identity_router(
    service: IdentityService,
    current_user: Callable,
    audit: Callable[..., None],
    api_error: Callable[..., None],
) -> APIRouter:
    router = APIRouter(prefix="/auth", tags=["identity"])

    def handle_error(exc: IdentityServiceError) -> None:
        api_error(exc.status_code, exc.error, exc.message, exc.details)

    @router.post("/register", response_model=AuthResponse)
    def register(req: RegisterRequest, request: Request):
        try:
            session = service.register(req.email, req.full_name, req.password)
        except IdentityServiceError as exc:
            handle_error(exc)
        user = session["user"]
        audit(
            "auth.register",
            actor=user,
            resource_type="user",
            resource_id=user["user_id"],
            request=request,
        )
        return session

    @router.post("/login", response_model=AuthResponse)
    def login(req: LoginRequest, request: Request):
        try:
            session = service.login(req.email, req.password)
        except IdentityServiceError as exc:
            handle_error(exc)
        user = session["user"]
        audit(
            "auth.login",
            actor=user,
            resource_type="user",
            resource_id=user["user_id"],
            request=request,
        )
        return session

    @router.get("/me", response_model=UserPublic)
    def auth_me(user: dict = Depends(current_user)):
        return service.public_user(user)

    @router.post("/logout")
    def auth_logout(request: Request, user: dict = Depends(current_user)):
        audit(
            "auth.logout",
            actor=user,
            resource_type="user",
            resource_id=user["user_id"],
            request=request,
        )
        return {"status": "ok"}

    @router.post("/forgot-password")
    def forgot_password(req: ForgotPasswordRequest, request: Request):
        try:
            user = service.request_password_reset(req.email)
        except IdentityServiceError as exc:
            handle_error(exc)
        audit(
            "auth.password_reset_requested",
            actor=user,
            resource_type="user",
            resource_id=user["user_id"],
            request=request,
        )
        return {"status": "ok"}

    @router.post("/reset-password")
    def reset_password(req: ResetPasswordRequest, request: Request):
        try:
            user = service.reset_password(req.token, req.password)
        except IdentityServiceError as exc:
            handle_error(exc)
        audit(
            "auth.password_reset_completed",
            actor=user,
            resource_type="user",
            resource_id=user["user_id"],
            request=request,
        )
        return {"status": "ok"}

    @router.get("/google/start")
    def google_auth_start():
        try:
            url = service.google_start_url()
        except OAuthFlowError as exc:
            url = service.oauth_error_url(exc.code, exc.message)
        return RedirectResponse(url, status_code=302)

    @router.get("/google/callback")
    def google_auth_callback(code: str = "", state: str = "", error: str = ""):
        try:
            result = service.google_callback(code, state, error)
        except OAuthFlowError as exc:
            return RedirectResponse(service.oauth_error_url(exc.code, exc.message), status_code=302)
        user = result["user"]
        audit(
            result["action"],
            actor=user,
            resource_type="user",
            resource_id=user["user_id"],
        )
        return RedirectResponse(service.oauth_success_url(result["session"]), status_code=302)

    return router
