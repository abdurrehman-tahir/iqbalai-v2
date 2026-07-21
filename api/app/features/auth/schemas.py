"""Auth schemas — T-016."""

from __future__ import annotations

from pydantic import BaseModel

from app.features.users.models import UserAccountStatus


class PostLoginResponse(BaseModel):
    """Response from POST /api/v1/auth/post-login."""

    user_id: str
    email: str
    role: str
    tenant_type: str = "school"
    district_id: str | None = None
    school_id: str | None = None
    is_first_login: bool
    # True when user has not yet accepted the current ToS
    tos_acceptance_required: bool
    current_tos_version_id: str | None
    account_status: str = UserAccountStatus.ACTIVE.value
    parent_state: str | None = None


class MeResponse(BaseModel):
    """Response from GET /api/v1/auth/me (T-245).

    Tokens are HttpOnly cookies now — the frontend can't decode them for
    display state (name/role in the shell nav, ownership checks). This is
    that read: the same claims AuthMiddleware already enriched from the DB
    on every authenticated request, just handed back as JSON.
    """

    user_id: str
    email: str
    role: str
    tenant_type: str = "school"
    district_id: str | None = None
    school_id: str | None = None
