"""Career document upload / list / delete / replace tests — SPEC §20, Phase 3."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import database as db_module
from app.models.career_document import CareerDocument
from app.models.career_profile import CareerProfile
from app.services import document_service
from tests.conftest import (
    make_minimal_docx,
    make_minimal_pdf,
    make_minimal_txt,
    make_scanned_looking_pdf,
)


# ─── Upload / extraction ──────────────────────────────────────────────────


def test_upload_document_persists_and_extracts_pdf(client: TestClient) -> None:
    r = client.post(
        "/api/career/documents",
        data={"kind": "resume"},
        files={"file": ("baseline.pdf", make_minimal_pdf(), "application/pdf")},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["kind"] == "resume"
    assert body["filename"] == "baseline.pdf"
    assert body["mime"] == "application/pdf"
    assert len(body["extracted_text_preview"]) > 0


def test_upload_document_persists_and_extracts_docx(client: TestClient) -> None:
    r = client.post(
        "/api/career/documents",
        data={"kind": "career_desc"},
        files={
            "file": (
                "career_desc.docx",
                make_minimal_docx(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["kind"] == "career_desc"
    assert body["mime"].endswith("wordprocessingml.document")
    assert "CareerFit" in body["extracted_text_preview"]


def test_upload_document_persists_and_extracts_txt(client: TestClient) -> None:
    r = client.post(
        "/api/career/documents",
        data={"kind": "portfolio"},
        files={"file": ("portfolio.txt", make_minimal_txt(), "text/plain")},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["kind"] == "portfolio"
    assert body["mime"] == "text/plain"


# ─── Rejection paths ──────────────────────────────────────────────────────


def test_upload_rejects_scanned_pdf(client: TestClient) -> None:
    """Grill Me #1 §12: min-chars gate on extracted text (proxy for OCR-only PDFs)."""
    r = client.post(
        "/api/career/documents",
        data={"kind": "resume"},
        files={"file": ("scanned.pdf", make_scanned_looking_pdf(), "application/pdf")},
    )
    assert r.status_code == 400
    body = r.json()
    assert body["error"] == "EmptyExtractedTextError"
    assert "OCR" in body["message"]


def test_upload_rejects_unknown_extension(client: TestClient) -> None:
    r = client.post(
        "/api/career/documents",
        data={"kind": "resume"},
        files={"file": ("evil.exe", b"MZ\x90\x00" * 100, "application/x-msdownload")},
    )
    assert r.status_code == 400
    assert r.json()["error"] == "InvalidUploadError"


def test_upload_rejects_over_size_limit(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Grill Me #1 Finding 13: explicit test for the size guard."""
    monkeypatch.setenv("MAX_UPLOAD_BYTES", "1024")  # 1 KB cap
    from app.config import reset_settings_cache

    reset_settings_cache()

    r = client.post(
        "/api/career/documents",
        data={"kind": "resume"},
        files={"file": ("big.pdf", make_minimal_pdf() * 200, "application/pdf")},
    )
    assert r.status_code == 413
    assert r.json()["error"] == "PayloadTooLargeError"


def test_upload_rejects_bad_kind(client: TestClient) -> None:
    r = client.post(
        "/api/career/documents",
        data={"kind": "job_posting"},  # not in CAREER_DOCUMENT_KINDS
        files={"file": ("x.pdf", make_minimal_pdf(), "application/pdf")},
    )
    assert r.status_code == 400
    assert "kind" in r.json()["message"]


# ─── Filename sanitisation (Grill Me #1 Finding 13) ───────────────────────


def test_sanitize_filename_blocks_path_traversal() -> None:
    # After rsplit on '/', only the trailing basename survives.
    assert document_service.sanitize_filename("../../../etc/passwd") == "passwd"
    assert document_service.sanitize_filename("..\\..\\Windows\\evil.pdf") == "evil.pdf"
    # Mixed separators too.
    assert document_service.sanitize_filename("/tmp/../etc\\shadow") == "shadow"


def test_sanitize_filename_preserves_korean() -> None:
    """Whitelist must keep Hangul precomposed characters."""
    assert document_service.sanitize_filename("이력서_배재억.pdf") == "이력서_배재억.pdf"
    assert document_service.sanitize_filename("경력기술서 (2026).docx") == "경력기술서_2026_.docx"


def test_sanitize_filename_caps_length() -> None:
    long_name = "a" * 500 + ".pdf"
    assert len(document_service.sanitize_filename(long_name)) <= 200


def test_sanitize_filename_returns_default_for_empty() -> None:
    assert document_service.sanitize_filename("") == "file"
    assert document_service.sanitize_filename("///") == "file"


# ─── List / one-per-kind / delete / replace ───────────────────────────────


def _upload_resume(client: TestClient, filename: str = "r.pdf") -> int:
    r = client.post(
        "/api/career/documents",
        data={"kind": "resume"},
        files={"file": (filename, make_minimal_pdf(), "application/pdf")},
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_list_documents_returns_all_kinds(client: TestClient) -> None:
    client.post(
        "/api/career/documents",
        data={"kind": "resume"},
        files={"file": ("r.pdf", make_minimal_pdf(), "application/pdf")},
    )
    client.post(
        "/api/career/documents",
        data={"kind": "portfolio"},
        files={"file": ("p.txt", make_minimal_txt(), "text/plain")},
    )
    r = client.get("/api/career/documents")
    assert r.status_code == 200
    kinds = {d["kind"] for d in r.json()}
    assert kinds == {"resume", "portfolio"}


def test_upload_replaces_previous_of_same_kind(client: TestClient) -> None:
    _upload_resume(client, filename="v1.pdf")
    _upload_resume(client, filename="v2.pdf")
    # Only the latest survives — the unique(kind) constraint is enforced by
    # a delete+insert cycle in the API.  (SQLite may reuse the primary key
    # after DELETE without AUTOINCREMENT, so we assert on filename, not id.)
    r = client.get("/api/career/documents")
    resume_rows = [d for d in r.json() if d["kind"] == "resume"]
    assert len(resume_rows) == 1
    assert resume_rows[0]["filename"] == "v2.pdf"


def test_delete_removes_row_and_file(client: TestClient) -> None:
    doc_id = _upload_resume(client)
    # Verify file exists first.
    session = db_module.SessionLocal()
    try:
        doc = session.get(CareerDocument, doc_id)
        assert doc is not None
        stored_path = Path(doc.stored_path)
        assert stored_path.exists()
    finally:
        session.close()

    r = client.delete(f"/api/career/documents/{doc_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["deleted_id"] == doc_id
    assert body["file_removed"] is True
    assert not stored_path.exists()


def test_delete_missing_returns_404(client: TestClient) -> None:
    r = client.delete("/api/career/documents/9999")
    assert r.status_code == 404
    assert r.json()["error"] == "NotFoundError"


def test_delete_referenced_career_document_blocked(client: TestClient) -> None:
    """Grill Me #1 Finding 7: application-level RESTRICT on referenced docs."""
    doc_id = _upload_resume(client)

    # Simulate a career profile referencing this doc.
    session = db_module.SessionLocal()
    try:
        session.add(
            CareerProfile(
                profile_json={"summary": "x"},
                source_doc_ids=[doc_id],
                mode="MOCK",
                provider="mock",
            )
        )
        session.commit()
    finally:
        session.close()

    r = client.delete(f"/api/career/documents/{doc_id}")
    assert r.status_code == 409
    body = r.json()
    assert body["error"] == "ReferencedDocumentError"
    assert doc_id in [] or body["referenced_by"]  # non-empty list


def test_delete_referenced_career_document_forced_marks_orphan(
    client: TestClient,
) -> None:
    doc_id = _upload_resume(client)
    session = db_module.SessionLocal()
    try:
        session.add(
            CareerProfile(
                profile_json={"summary": "x"},
                source_doc_ids=[doc_id],
                mode="MOCK",
                provider="mock",
            )
        )
        session.commit()
    finally:
        session.close()

    r = client.delete(f"/api/career/documents/{doc_id}?force=true")
    assert r.status_code == 200
    body = r.json()
    assert body["deleted_id"] == doc_id
    assert body["file_removed"] is True
    assert len(body["orphaned_profiles"]) == 1


def test_replace_document_atomic_success(client: TestClient) -> None:
    """Grill Me #1 §17: DB row updates before old file is unlinked."""
    doc_id = _upload_resume(client, filename="original.pdf")

    session = db_module.SessionLocal()
    try:
        original_path = Path(session.get(CareerDocument, doc_id).stored_path)
    finally:
        session.close()

    assert original_path.exists()

    r = client.post(
        f"/api/career/documents/{doc_id}/replace",
        files={
            "file": (
                "replacement.pdf",
                make_minimal_pdf(body_text="Replacement resume content " * 20),
                "application/pdf",
            )
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"] == doc_id
    assert body["filename"] == "replacement.pdf"

    session = db_module.SessionLocal()
    try:
        doc = session.get(CareerDocument, doc_id)
        new_path = Path(doc.stored_path)
        assert new_path.exists()
        assert new_path != original_path
        # Old file was unlinked after the DB commit.
        assert not original_path.exists()
    finally:
        session.close()


# ─── Persistence across sessions (Grill Me #1 §17 acceptance) ────────────


def test_upload_survives_restart(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Upload with one app instance, then re-open a new app pointing at the
    same on-disk DB + uploads dir, and verify everything still resolves.

    Uses file-backed SQLite so a fresh engine sees the persisted state; the
    default in-memory fixture would obviously lose everything.
    """
    from sqlalchemy import create_engine, event
    from sqlalchemy.orm import sessionmaker
    import sqlite3 as _sq3

    db_path = tmp_path / "restart.db"
    uploads = tmp_path / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)

    def build_engine():
        eng = create_engine(
            f"sqlite:///{db_path.as_posix()}",
            connect_args={"check_same_thread": False},
            future=True,
        )

        @event.listens_for(eng, "connect")
        def _pragma(conn, _rec):  # noqa: ANN001
            if isinstance(conn, _sq3.Connection):
                cur = conn.cursor()
                cur.execute("PRAGMA foreign_keys=ON")
                cur.close()

        return eng

    # ── First "process" ────────────────────────────────────────────────
    eng = build_engine()
    monkeypatch.setattr(db_module, "engine", eng)
    monkeypatch.setattr(
        db_module,
        "SessionLocal",
        sessionmaker(bind=eng, autoflush=False, expire_on_commit=False, future=True),
    )
    monkeypatch.setattr(db_module, "UPLOADS_ROOT", uploads)
    from app.services import document_service as ds

    monkeypatch.setattr(ds, "UPLOADS_ROOT", uploads)

    import app.models  # noqa: F401

    db_module.Base.metadata.create_all(bind=eng)

    from app.main import create_app

    app = create_app()
    with TestClient(app) as c:
        r = c.post(
            "/api/career/documents",
            data={"kind": "resume"},
            files={"file": ("survives.pdf", make_minimal_pdf(), "application/pdf")},
        )
        assert r.status_code == 200
        doc_id = r.json()["id"]

    # ── Second "process" — new engine, same files ──────────────────────
    eng.dispose()
    eng2 = build_engine()
    monkeypatch.setattr(db_module, "engine", eng2)
    monkeypatch.setattr(
        db_module,
        "SessionLocal",
        sessionmaker(bind=eng2, autoflush=False, expire_on_commit=False, future=True),
    )

    app2 = create_app()
    with TestClient(app2) as c:
        r = c.get("/api/career/documents")
        assert r.status_code == 200
        rows = r.json()
        assert any(d["id"] == doc_id for d in rows)
        target = next(d for d in rows if d["id"] == doc_id)
        assert target["filename"] == "survives.pdf"

    # The stored file must still be on disk.
    session2 = db_module.SessionLocal()
    try:
        stored = session2.execute(
            select(CareerDocument).where(CareerDocument.id == doc_id)
        ).scalar_one()
        assert Path(stored.stored_path).exists()
    finally:
        session2.close()
