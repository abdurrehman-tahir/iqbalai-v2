"""User Pydantic schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.features.users.models import UserRole


class UserRead(BaseModel):
    """User response schema."""

    id: str
    authentik_id: str
    email: str
    display_name: str
    role: UserRole
    school_id: str | None
    district_id: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    """User creation schema (called on first OIDC login)."""

    authentik_id: str
    email: str
    display_name: str
    role: UserRole
    school_id: str | None = None
    district_id: str | None = None


class UserUpdate(BaseModel):
    """User update schema."""

    display_name: str | None = None
    school_id: str | None = None
    district_id: str | None = None
