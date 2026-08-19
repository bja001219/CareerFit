"""JobPosting ORM model.

``stored_path`` is populated only when ``source_type == "pdf"``; url / text
postings persist raw text in ``raw_text`` and keep ``stored_path`` NULL.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

JOB_SOURCE_TYPES: tuple[str, ...] = ("url", "pdf", "text")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class JobPosting(Base):
    __tablename__ = "job_postings"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    company: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    source_ref: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    stored_path: Mapped[str | None] = mapped_column(String(400), nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    posting_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, index=True
    )
