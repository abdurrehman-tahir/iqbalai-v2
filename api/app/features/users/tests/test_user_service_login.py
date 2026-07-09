"""Tests for OIDC login user reconciliation (invite authentik_id vs JWT sub)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.features.users.models import User, UserAccountStatus, UserRole
from app.features.users.service import UserService


def _district_admin() -> User:
    return User(
        id="district-1",
        authentik_id="36",
        email="admin@district.edu",
        display_name="District Admin",
        role=UserRole.DISTRICT_ADMIN,
        status=UserAccountStatus.ACTIVE,
        district_id="district-abc",
    )


def _student_duplicate() -> User:
    return User(
        id="student-1",
        authentik_id="jwt-sub-hash",
        email="admin@district.edu",
        display_name="District Admin",
        role=UserRole.STUDENT,
        status=UserAccountStatus.ACTIVE,
    )


@pytest.mark.asyncio
async def test_get_or_create_from_jwt_reconciles_invited_user_by_email() -> None:
    session = AsyncMock()
    svc = UserService(session)
    district = _district_admin()
    student = _student_duplicate()

    repo = AsyncMock()
    repo.get_by_authentik_id.return_value = None
    repo.list_by_email.return_value = [district, student]
    repo.update.side_effect = lambda user: user
    svc._repo = repo

    user, is_first_login = await svc.get_or_create_from_jwt(
        {
            "sub": "jwt-sub-hash",
            "email": "admin@district.edu",
            "name": "District Admin",
        }
    )

    assert is_first_login is False
    assert user.role == UserRole.DISTRICT_ADMIN
    assert user.authentik_id == "jwt-sub-hash"
    assert student.deleted_at is not None
    assert repo.update.await_count == 2
