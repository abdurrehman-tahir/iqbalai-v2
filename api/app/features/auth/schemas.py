"""Auth schemas — T-016."""

from __future__ import annotations

from pydantic import BaseModel

from app.features.users.models import UserRole


class PostLoginResponse(BaseModel):
    """Response from POST /api/v1/auth/post-login."""

    user_id: str
    email: str
    role: UserRole
    district_id: str | None = None
    school_id: str | None = None
    is_first_login: bool
    # True when user has not yet accepted the current ToS
    tos_acceptance_required: bool
    current_tos_version_id: str | None
