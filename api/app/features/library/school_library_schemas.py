"""School Content Library Pydantic schemas — T-055 / T-058."""

from __future__ import annotations

from datetime import datetime
from typing import Any

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
    topic_tree_jsonb: dict[str, Any] | None = None
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


class SchoolLibraryListResponse(BaseModel):
    """Paginated list of school library items visible to the caller."""

    items: list[SchoolLibraryItemRead]
    total: int
