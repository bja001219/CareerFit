"""CareerFit FastAPI entrypoint (Phase 2 foundation).

Wires:
* lifespan → :pyfunc:`app.database.init_db`
* CORS middleware from :pyattr:`app.config.Settings.cors_allow_origins`
* :pymod:`app.api.health` router (later phases add more routers)
* Global :pyclass:`app.models.errors.CareerFitError` handler

Later phases plug in career_documents / career_profile / job_posting /
fit_analysis / history routers alongside health.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import career_documents, health
from app.api.errors import register_error_handlers
from app.config import get_settings
from app.database import init_db


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


def create_app() -> FastAPI:
    settings = get_settings()  # boot-time weight validation happens here

    app = FastAPI(
        title="CareerFit",
        description="Career × Job Posting Fit Analyzer",
        version="0.2.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(career_documents.router)
    return app


app = create_app()
