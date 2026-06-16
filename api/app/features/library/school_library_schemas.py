"""School Content Library Pydantic schemas — T-055."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SchoolLibraryUploadRequest(BaseModel):
    """Metadata for a school library PDF upload (file sent as multipart)."""

    title: str = Field(..., min_length=1, max_length=500)
    content_type: str = Field(default="reference", pattern="^(curriculum|reference)$")
    language: str = Field(default="en", pattern="^(en|ur|sd|ps)$")
    subject_id: str | None = Field(default=None, max_length=36)
    grade_level_ordinal: int | None = Field(default=None, ge=1, le=16)
    visibility: str = Field(default="private", pattern="^(private|school_public)$")


class SchoolLibraryItemRead(BaseModel):
    """School library item returned to callers."""

    model_config = {"from_attributes": True}

    id: str
    school_id: str
    title: str
    content_type: str
    language: str
    subject_id: str | None
    grade_level_ordinal: int | None
    storage_key: str
    sha256: str
    ingestion_status: str
    created_by: str
    visibility: str
    created_at: datetime
    updated_at: datetime


class SchoolLibraryUploadResponse(BaseModel):
    """Response after POST /school/library — 202 Accepted."""

    item: SchoolLibraryItemRead
    storage_deduplicated: bool
    selection_created: bool
    message: str = "Upload accepted; ingestion will run in a later step."
