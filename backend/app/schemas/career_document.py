"""Career document API schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CareerDocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    filename: str
    mime: str
    size_bytes: int
    uploaded_at: datetime
    extracted_text_preview: str = ""


class DeleteResult(BaseModel):
    deleted_id: int
    file_removed: bool


class ForceDeleteAcknowledgement(BaseModel):
    """Returned as the ``force`` response body describing what was orphaned."""

    deleted_id: int
    file_removed: bool
    orphaned_profiles: list[int]
