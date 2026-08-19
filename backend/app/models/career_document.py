"""CareerDocument ORM model.

One document per ``kind`` (resume / career_desc / portfolio).  Uploaded PDF
for a job posting lives in :pymod:`app.models.job_posting`, not here — the
uniqueness scope is deliberately restricted to career kinds.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

CAREER_DOCUMENT_KINDS: tuple[str, ...] = ("resume", "career_desc", "portfolio")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CareerDocument(Base):
    __tablename__ = "career_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    filename: Mapped[str] = mapped_column(String(300), nullable=False)
    stored_path: Mapped[str] = mapped_column(String(400), nullable=False)
    mime: Mapped[str] = mapped_column(String(80), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    extracted_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    __table_args__ = (
        UniqueConstraint("kind", name="uq_career_documents_kind"),
    )
