"""Pydantic request/response schemas.

Later phases will add career/job/fit schemas here.  Phase 2 only needs the
health response.
"""
from app.schemas.health import HealthResponse

__all__ = ["HealthResponse"]
