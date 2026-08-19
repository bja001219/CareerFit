from __future__ import annotations

from fastapi import APIRouter

from app.config import get_settings
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        mode=settings.mode,
        effective_mode=settings.effective_mode,
        provider=settings.active_provider,
        model=settings.active_model,
        fallback_reason=settings.fallback_reason,
    )
