from __future__ import annotations

from typing import Callable

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from services.system_status_service import SystemStatusService


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


def create_system_router(
    service: SystemStatusService,
    require_roles: Callable[..., Callable],
) -> APIRouter:
    router = APIRouter(tags=["system"])

    @router.get("/health", response_model=HealthResponse)
    def health_check():
        return service.health()

    @router.get("/ops/status")
    def ops_status(user: dict = Depends(require_roles("instructor", "admin"))):
        return service.ops_status(user)

    @router.get("/ops/metrics")
    def ops_metrics(user: dict = Depends(require_roles("admin"))):
        return service.ops_metrics(user)

    return router
