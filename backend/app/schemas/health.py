"""Health check response schema.

The frontend renders its Mode badge from ``effective_mode`` and shows
``fallback_reason`` in the tooltip when it differs from ``mode`` — the
distinction is the Grill Me #1 Finding 8 fix.
"""
from __future__ import annotations

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    mode: str  # user-configured (MOCK / LIVE)
    effective_mode: str  # what actually runs (MOCK / LIVE)
    provider: str  # mock / gemini / openai
    model: str
    fallback_reason: str | None = None
