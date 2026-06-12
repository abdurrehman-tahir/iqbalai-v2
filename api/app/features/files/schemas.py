"""Upload pipeline Pydantic schemas."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


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
    """Response for GET /uploads/{id}.

    `upload_id` is the public name for the record's primary key (`id`). The
    validation alias lets `model_validate(record)` read it straight off the
    ORM row, while the serialized output keeps the `upload_id` field name so the
    API contract (and the generated typed client) is unchanged.
    """

    # populate_by_name keeps the explicit `UploadStatusResponse(upload_id=...)`
    # construction path working alongside from_attributes/model_validate.
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    upload_id: str = Field(validation_alias=AliasChoices("upload_id", "id"))
    status: UploadStatus
    profile: str
    filename: str
    size_bytes: int
    sha256: str
    minio_key: str
    created_at: datetime
