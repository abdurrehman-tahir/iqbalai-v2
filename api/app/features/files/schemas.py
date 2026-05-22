"""Upload pipeline Pydantic schemas."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class UploadStatus(StrEnum):
    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"
    DUPLICATE = "duplicate"


class UploadInitiated(BaseModel):
    """Response returned immediately after upload (202 Accepted)."""

    upload_id: str
    status: UploadStatus
    status_url: str
    message: str = ""


class UploadStatusResponse(BaseModel):
    """Response for GET /uploads/{id}."""

    upload_id: str
    status: UploadStatus
    profile: str
    filename: str
    size_bytes: int
    sha256: str
    minio_key: str
    created_at: datetime

    model_config = {"from_attributes": True}
