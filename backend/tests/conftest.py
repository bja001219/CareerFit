"""Shared pytest fixtures.

Each test gets a fresh in-memory SQLite + isolated uploads directory so
state never leaks across tests.  Env is cleared before ``get_settings`` is
reset so ``MOCK_MODE`` etc. are read from whatever the individual test set
with ``monkeypatch``.

PDF / DOCX fixtures are generated in memory so we neither commit binary
blobs nor depend on external tools.  See :pyfunc:`make_minimal_pdf` and
:pyfunc:`make_minimal_docx`.
"""
from __future__ import annotations

import io
from collections.abc import Iterator
from pathlib import Path

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
def tmp_uploads_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Point ``app.database.UPLOADS_ROOT`` at an isolated per-test directory.

    Anywhere ``document_service`` writes should end up under ``tmp_path``.
    """
    fake_uploads = tmp_path / "uploads"
    fake_uploads.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(db_module, "UPLOADS_ROOT", fake_uploads)
    from app.services import document_service as ds

    monkeypatch.setattr(ds, "UPLOADS_ROOT", fake_uploads)
    return fake_uploads


@pytest.fixture()
def in_memory_db(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Swap the module-level engine/SessionLocal for an in-memory SQLite.

    Uses ``StaticPool`` so every connection sees the same underlying
    ``:memory:`` database — the default pool would hand out fresh empty
    databases to different threads and the ORM would see "no such table".
    """
    from sqlalchemy import event
    from sqlalchemy.pool import StaticPool
    import sqlite3

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )

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
def client(in_memory_db: None, tmp_uploads_root: Path) -> Iterator[TestClient]:
    """FastAPI TestClient with per-test in-memory DB + isolated uploads dir."""
    # Import inside the fixture so create_app() sees the patched engine.
    from app.main import create_app

    app = create_app()
    with TestClient(app) as tc:
        yield tc


# ─── Sample document generators ───────────────────────────────────────────


def make_minimal_pdf(body_text: str = None) -> bytes:  # type: ignore[assignment]
    """Emit a valid single-page PDF whose text is extractable by pypdf.

    Byte offsets in the xref table must be exact — this is the fragile
    part of hand-rolling a PDF.  Kept minimal on purpose: one page, one
    Helvetica text object, one content stream.
    """
    if body_text is None:
        # Give pypdf enough characters to clear MIN_EXTRACTED_CHARS (200).
        body_text = (
            "CareerFit sample resume text. "
            "Backend engineer with 5 years of Python and FastAPI experience. "
            "Familiar with PostgreSQL, SQLAlchemy, and Docker. "
            "Built REST APIs at scale and handled service reliability incidents. "
            "This is a fixture used for automated tests only, no real person."
        )
    escaped = (
        body_text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    )
    # Split into multiple lines so pypdf's page.extract_text() emits newlines.
    lines = [escaped[i : i + 60] for i in range(0, len(escaped), 60)]
    content_body_parts = ["BT", "/F1 12 Tf", "72 720 Td"]
    for i, ln in enumerate(lines):
        if i > 0:
            content_body_parts.append("0 -14 Td")
        content_body_parts.append(f"({ln}) Tj")
    content_body_parts.append("ET")
    content_stream = "\n".join(content_body_parts).encode("ascii")

    objects: list[bytes] = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj",
        (
            b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Contents 5 0 R /Resources << /Font << /F1 4 0 R >> >> >>\nendobj"
        ),
        b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj",
        (
            b"5 0 obj\n<< /Length "
            + str(len(content_stream)).encode()
            + b" >>\nstream\n"
            + content_stream
            + b"\nendstream\nendobj"
        ),
    ]

    header = b"%PDF-1.4\n"
    body = header
    offsets: list[int] = [0]
    for obj in objects:
        offsets.append(len(body))
        body += obj + b"\n"

    xref_offset = len(body)
    xref = b"xref\n0 " + str(len(objects) + 1).encode() + b"\n"
    xref += b"0000000000 65535 f \n"
    for off in offsets[1:]:
        xref += f"{off:010d} 00000 n \n".encode()

    trailer = (
        b"trailer\n<< /Size "
        + str(len(objects) + 1).encode()
        + b" /Root 1 0 R >>\nstartxref\n"
        + str(xref_offset).encode()
        + b"\n%%EOF"
    )
    return body + xref + trailer


def make_minimal_docx(body_text: str = None) -> bytes:  # type: ignore[assignment]
    """Emit a valid DOCX via python-docx as bytes."""
    from docx import Document

    if body_text is None:
        body_text = (
            "CareerFit sample career description. "
            "Led migration from monolith to microservices across 4 teams. "
            "Owned reliability SLOs and reduced p99 latency by 40 percent. "
            "Built the CI pipeline and mentored 3 junior engineers. "
            "This document is a synthetic test fixture, no real person."
        )
    doc = Document()
    for paragraph in body_text.split("\n"):
        doc.add_paragraph(paragraph)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def make_minimal_txt(body_text: str = None, encoding: str = "utf-8") -> bytes:  # type: ignore[assignment]
    if body_text is None:
        body_text = (
            "CareerFit sample portfolio. Personal project descriptions. "
            "Real-time monitoring dashboard using React and websockets. "
            "AI-assisted code review pipeline integrating GitHub Actions. "
            "Open-source contributions to the FastAPI ecosystem. "
            "Fixture only — no real personal data."
        )
    return body_text.encode(encoding)


def make_scanned_looking_pdf() -> bytes:
    """Empty PDF (no text) — used to test the OCR-not-supported branch."""
    return make_minimal_pdf(body_text="x")
