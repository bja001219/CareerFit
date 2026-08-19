"""Career document upload / list / delete / replace endpoints.

Delete cascades to any career_profile that references the document via
``source_doc_ids``.  Since the FK is JSON-embedded, we enforce this at
application level: default is 409 with the list of referencing profiles;
pass ``?force=true`` to delete anyway (the referenced profiles still exist
but their evidence will be marked ``orphaned`` on re-verify).
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.models.career_document import CAREER_DOCUMENT_KINDS, CareerDocument
from app.models.career_profile import CareerProfile
from app.models.errors import (
    InvalidUploadError,
    NotFoundError,
    ReferencedDocumentError,
)
from app.schemas.career_document import (
    CareerDocumentOut,
    DeleteResult,
    ForceDeleteAcknowledgement,
)
from app.services import document_service

router = APIRouter(prefix="/api/career/documents", tags=["career-documents"])


PREVIEW_CHARS = 240


def _to_out(doc: CareerDocument) -> CareerDocumentOut:
    preview = (doc.extracted_text or "").strip()[:PREVIEW_CHARS]
    return CareerDocumentOut(
        id=doc.id,
        kind=doc.kind,
        filename=doc.filename,
        mime=doc.mime,
        size_bytes=doc.size_bytes,
        uploaded_at=doc.uploaded_at,
        extracted_text_preview=preview,
    )


def _find_referencing_profiles(db: Session, doc_id: int) -> list[int]:
    profiles = db.execute(select(CareerProfile)).scalars().all()
    return [
        p.id for p in profiles
        if isinstance(p.source_doc_ids, list) and doc_id in p.source_doc_ids
    ]


@router.post("", response_model=CareerDocumentOut)
async def upload_document(
    kind: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> CareerDocumentOut:
    if kind not in CAREER_DOCUMENT_KINDS:
        raise InvalidUploadError(
            f"'kind' 는 다음 중 하나여야 합니다: {', '.join(CAREER_DOCUMENT_KINDS)}"
        )
    if not file.filename:
        raise InvalidUploadError("파일명이 없습니다.")

    content = await file.read()
    stored_path, mime, size, text = document_service.save_career_document(
        kind=kind,
        filename=file.filename,
        content=content,
        max_bytes=settings.max_upload_bytes,
    )

    # Enforce one-per-kind: delete previous row + file if present, then insert.
    existing = db.execute(
        select(CareerDocument).where(CareerDocument.kind == kind)
    ).scalar_one_or_none()
    if existing is not None:
        old_path = Path(existing.stored_path)
        db.delete(existing)
        db.commit()
        document_service.replace_document_atomic(
            old_path=old_path, new_stored_path=stored_path
        )

    doc = CareerDocument(
        kind=kind,
        filename=document_service.sanitize_filename(file.filename),
        stored_path=str(stored_path),
        mime=mime,
        size_bytes=size,
        extracted_text=text,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return _to_out(doc)


@router.get("", response_model=list[CareerDocumentOut])
def list_documents(db: Session = Depends(get_db)) -> list[CareerDocumentOut]:
    docs = db.execute(
        select(CareerDocument).order_by(CareerDocument.uploaded_at.desc())
    ).scalars().all()
    return [_to_out(d) for d in docs]


@router.delete("/{doc_id}", response_model=DeleteResult | ForceDeleteAcknowledgement)
def delete_document(
    doc_id: int,
    force: bool = False,
    db: Session = Depends(get_db),
):
    doc = db.get(CareerDocument, doc_id)
    if doc is None:
        raise NotFoundError(f"CareerDocument id={doc_id} 를 찾을 수 없습니다.")

    referencing = _find_referencing_profiles(db, doc_id)
    if referencing and not force:
        raise ReferencedDocumentError(
            referenced_by=referencing,
            message=(
                f"이 문서를 참조하는 이전 프로필 {len(referencing)}개가 있습니다: {referencing}. "
                "무시하고 삭제하려면 ?force=true 를 붙여 다시 시도하세요."
            ),
        )

    path = Path(doc.stored_path)
    db.delete(doc)
    db.commit()

    file_removed = False
    if path.exists():
        try:
            path.unlink()
            file_removed = True
        except OSError:
            pass

    if force and referencing:
        return ForceDeleteAcknowledgement(
            deleted_id=doc_id,
            file_removed=file_removed,
            orphaned_profiles=referencing,
        )
    return DeleteResult(deleted_id=doc_id, file_removed=file_removed)


@router.post("/{doc_id}/replace", response_model=CareerDocumentOut)
async def replace_document(
    doc_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> CareerDocumentOut:
    doc = db.get(CareerDocument, doc_id)
    if doc is None:
        raise NotFoundError(f"CareerDocument id={doc_id} 를 찾을 수 없습니다.")

    if not file.filename:
        raise InvalidUploadError("파일명이 없습니다.")

    content = await file.read()
    stored_path, mime, size, text = document_service.save_career_document(
        kind=doc.kind,
        filename=file.filename,
        content=content,
        max_bytes=settings.max_upload_bytes,
    )

    old_path = Path(doc.stored_path)
    doc.filename = document_service.sanitize_filename(file.filename)
    doc.stored_path = str(stored_path)
    doc.mime = mime
    doc.size_bytes = size
    doc.extracted_text = text
    db.commit()
    db.refresh(doc)

    # DB is authoritative; unlink previous file after commit.
    document_service.replace_document_atomic(
        old_path=old_path, new_stored_path=stored_path
    )
    return _to_out(doc)
