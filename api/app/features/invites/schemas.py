"""Pydantic schemas for user invitation endpoints (T-030)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.features.users.models import UserRole


class AdminUserInviteCreate(BaseModel):
    """Payload for POST /admin/users — invite a next-level admin."""

    email: str = Field(min_length=3, max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    display_name: str = Field(min_length=1, max_length=255)
    role: UserRole
    district_id: str | None = None
    school_id: str | None = None
    grade_scope: list[str] | None = Field(default=None, min_length=1)


class UserInviteRead(BaseModel):
    id: str
    email: str
    display_name: str
    invited_role: UserRole
    district_id: str | None
    school_id: str | None
    status: str
    expires_at: datetime
    resent_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class AcceptInviteRequest(BaseModel):
    token: str = Field(min_length=16)
    action: Literal["accept", "reject"]
    password: str | None = Field(default=None, min_length=8, max_length=128)
    display_name: str | None = Field(default=None, min_length=1, max_length=255)


class AcceptInviteResponse(BaseModel):
    status: str
    email: str | None = None
    message: str
