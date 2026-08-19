"""Global exception handler.

All :pyclass:`app.models.errors.CareerFitError` subclasses are routed through
one handler: the class carries its own HTTP status, and any structured extra
fields (``existing_id`` on ``DuplicateAnalysisError`` etc.) are lifted into
the JSON body so the frontend can act on them without regex-parsing text.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.models.errors import (
    CareerFitError,
    DuplicateAnalysisError,
    ReferencedDocumentError,
)

logger = logging.getLogger(__name__)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(CareerFitError)
    async def _handle_careerfit(_request: Request, exc: CareerFitError) -> JSONResponse:
        body: dict[str, object] = {
            "error": type(exc).__name__,
            "message": exc.message,
        }
        if isinstance(exc, DuplicateAnalysisError):
            body["existing_id"] = exc.existing_id
        if isinstance(exc, ReferencedDocumentError):
            body["referenced_by"] = exc.referenced_by

        # Keep server logs verbose; user response stays minimal.
        logger.warning("%s: %s", type(exc).__name__, exc.message)
        return JSONResponse(status_code=exc.status_code, content=body)
