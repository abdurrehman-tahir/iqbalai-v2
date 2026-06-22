"""Independent private pool Pydantic schemas — T-074."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class IndependentPersonalUploadRequest(BaseModel):
    """Metadata for an independent private pool PDF upload."""

    title: str = Field(..., min_length=1, max_length=500)
    content_type: str = Field(default="reference", pattern="^(curriculum|reference)$")
    language: str = Field(default="en", pattern="^(en|ur|sd|ps)$")


class IndependentPersonalContentRead(BaseModel):
    """Private pool item returned to the owning independent user."""

    model_config = {"from_attributes": True}

    id: str
    user_id: str
    content_type: str
    title: str
    file_key: str
    file_sha256: str
    status: str
    structured_parsing_status: str | None = None
    topic_tree_jsonb: dict[str, Any] | None = None
    vector_collection: str
    ingestion_error: str | None = None
    created_at: datetime
    updated_at: datetime


class IndependentPersonalUploadResponse(BaseModel):
    """Response after POST /independent/personal-content — 202 Accepted."""

    item: IndependentPersonalContentRead
    storage_deduplicated: bool
    message: str = "Upload accepted; ingestion queued on the ingestion worker."


class IndependentPersonalListResponse(BaseModel):
    """Paginated list of the caller's private pool items."""

    items: list[IndependentPersonalContentRead]
    total: int
