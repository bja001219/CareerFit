"""CareerProfile ORM model.

No ``is_current`` boolean — Grill Me #1 Finding 6 (race-free): the "current"
profile is always the latest by ``created_at`` (see
``api.career_profile.get_current``).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CareerProfile(Base):
    __tablename__ = "career_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    source_doc_ids: Mapped[list[int]] = mapped_column(JSON, nullable=False, default=list)
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, index=True
    )
