"""Pydantic v2 schemas for the notifications feature (T-023)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NotificationRead(BaseModel):
    """Read schema for a single notification row."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    recipient_user_id: str
    feature_namespace: str
    template_key: str
    title: str
    body: str
    is_read: bool
    read_at: datetime | None
    school_id: str | None
    created_at: datetime


class NotificationListResponse(BaseModel):
    """Paginated notification list with unread counter for the bell badge."""

    items: list[NotificationRead]
    total: int
    unread_count: int
