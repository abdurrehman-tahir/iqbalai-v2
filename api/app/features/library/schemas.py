"""Platform Library Pydantic schemas — T-024."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class LibraryBookUploadRequest(BaseModel):
    """Fields provided at upload time (multipart form carries the file separately)."""

    title: str = Field(..., min_length=1, max_length=500)
    content_type: str = Field(default="reference", pattern="^(curriculum|reference)$")
    subject_tag: str | None = Field(default=None, max_length=255)
    grade_range_min: int | None = Field(default=None, ge=1, le=16)
    grade_range_max: int | None = Field(default=None, ge=1, le=16)
    language: str = Field(default="en", pattern="^(en|ur|sd|ps)$")


class LibraryBookRead(BaseModel):
    """Full book record returned to the caller."""

    model_config = {"from_attributes": True}

    id: str
    upload_id: str
    title: str
    content_type: str
    subject_tag: str | None
    grade_range_min: int | None
    grade_range_max: int | None
    language: str
    sha256: str
    status: str
    qdrant_collection: str
    chunk_count: int | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class LibraryUploadResponse(BaseModel):
    """Returned after POST /admin/library — 202 Accepted."""

    book_id: str
    upload_id: str
    status: str
    message: str = "Upload accepted; ingestion queued on the ingestion worker."


class LibraryBookListResponse(BaseModel):
    """Paginated list of platform reference books."""

    items: list[LibraryBookRead]
    total: int
