"""Auth schemas — T-016 (post-login) + M-07b T-240 (BFF login/reset)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.features.users.models import UserAccountStatus

# Matches the codebase convention (independent_signup) — avoids the email-validator
# dependency that `pydantic.EmailStr` pulls in.
_EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


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


class LoginRequest(BaseModel):
    """Credentials for POST /api/v1/auth/login (BFF — M-07b T-240)."""

    email: str = Field(min_length=3, max_length=255, pattern=_EMAIL_PATTERN)
    password: str = Field(min_length=1)


class LoginResponse(PostLoginResponse):
    """Login result — session is carried by HttpOnly cookies (M-07b T-244)."""

    pass


class ForgotPasswordRequest(BaseModel):
    """Email for POST /api/v1/auth/forgot-password (always returns 200)."""

    email: str = Field(min_length=3, max_length=255, pattern=_EMAIL_PATTERN)


class ResetPasswordRequest(BaseModel):
    """Token + new password for POST /api/v1/auth/reset-password (M-07b T-243)."""

    token: str = Field(min_length=1, max_length=512)
    new_password: str = Field(min_length=8, max_length=128)
