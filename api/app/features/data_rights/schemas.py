"""Data rights API schemas — T-084."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.features.data_rights.models import DataRightsRequestStatus, DataRightsRequestType


class DataRightsRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    request_type: DataRightsRequestType
    status: DataRightsRequestStatus
    requested_at: datetime
    ready_at: datetime | None = None
    expires_at: datetime | None = None
    deletion_scheduled_at: datetime | None = None
    completed_at: datetime | None = None
    cancelled_at: datetime | None = None
    download_available: bool = False


class DataRightsStatusRead(BaseModel):
    export_request: DataRightsRequestRead | None = None
    deletion_request: DataRightsRequestRead | None = None
    export_policy_message: str
    deletion_policy_message: str


class DataRightsDeletionCreate(BaseModel):
    confirm: bool = Field(
        ...,
        description="Must be true to acknowledge the 30-day grace period and review queue.",
    )
