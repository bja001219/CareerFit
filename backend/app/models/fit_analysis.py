"""FitAnalysis ORM model.

Two hard database-level invariants:

* :sqlfk:`career_profile_id` and :sqlfk:`job_posting_id` are
  ``ON DELETE CASCADE`` so deleting a profile or posting cleans up analyses
  that would otherwise dangle (Grill Me #1 Finding 7).
* ``UniqueConstraint(career_profile_id, job_posting_id)`` gives us the 409
  idempotency guarantee (Grill Me #1 Finding 12) without a race window.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class FitAnalysis(Base):
    __tablename__ = "fit_analyses"

    id: Mapped[int] = mapped_column(primary_key=True)
    career_profile_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("career_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_posting_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("job_postings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    analysis_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    overall_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    verdict: Mapped[str] = mapped_column(String(30), nullable=False, default="Insufficient Data")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, index=True
    )

    __table_args__ = (
        UniqueConstraint(
            "career_profile_id", "job_posting_id",
            name="uq_fit_analyses_profile_posting",
        ),
    )
