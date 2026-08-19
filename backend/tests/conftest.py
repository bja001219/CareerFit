"""Shared pytest fixtures.

Each test gets a fresh in-memory SQLite so state never leaks across tests.
The env is cleared before ``get_settings`` is reset so ``MOCK_MODE`` etc. are
read from whatever the individual test set with ``monkeypatch``.
"""
from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import database as db_module
from app.config import reset_settings_cache


# Env vars that Settings reads.  Cleared per-test so nothing leaks from the
# host `.env`.  Individual tests re-set what they need via monkeypatch.
_SETTINGS_ENV_KEYS = (
    "MOCK_MODE",
    "LLM_PROVIDER",
    "GEMINI_API_KEY",
    "GEMINI_MODEL",
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
    "MAX_UPLOAD_BYTES",
    "MAX_URL_BYTES",
    "CORS_ALLOW_ORIGINS",
    "WEIGHT_RESPONSIBILITY",
    "WEIGHT_REQUIREMENT",
    "WEIGHT_TECH",
    "WEIGHT_EXPERIENCE",
    "WEIGHT_PREFERRED",
)


@pytest.fixture(autouse=True)
def _clean_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Isolate each test from host env + prior get_settings() cache."""
    for key in _SETTINGS_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    reset_settings_cache()
    yield
    reset_settings_cache()


@pytest.fixture()
def in_memory_db(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Swap the module-level engine/SessionLocal for an in-memory SQLite.

    Any code that imports ``app.database.SessionLocal`` after this fixture
    activates will see the isolated engine.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        future=True,
    )
    # Re-attach the PRAGMA foreign_keys=ON listener from the real module.
    from sqlalchemy import event
    import sqlite3

    @event.listens_for(engine, "connect")
    def _pragma(dbapi_connection, _record):  # noqa: ANN001
        if isinstance(dbapi_connection, sqlite3.Connection):
            cur = dbapi_connection.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)

    monkeypatch.setattr(db_module, "engine", engine)
    monkeypatch.setattr(db_module, "SessionLocal", TestSession)

    # Create schema on the new engine.
    import app.models  # noqa: F401 — register models

    db_module.Base.metadata.create_all(bind=engine)
    yield
    engine.dispose()


@pytest.fixture()
def client(in_memory_db: None) -> Iterator[TestClient]:
    """FastAPI TestClient with per-test in-memory DB."""
    # Import inside the fixture so create_app() sees the patched engine.
    from app.main import create_app

    app = create_app()
    with TestClient(app) as tc:
        yield tc
