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


@pytest.mark.asyncio
async def test_get_or_create_from_jwt_reconciles_role_from_claim() -> None:
    """Missing `iqbalai` scope on first login can persist role=student; fix on re-login."""
    session = AsyncMock()
    svc = UserService(session)
    trapped = User(
        id="u-1",
        authentik_id="jwt-sub",
        email="platform.admin@iqbalai.dev",
        display_name="Platform Admin",
        role=UserRole.STUDENT,
        status=UserAccountStatus.ACTIVE,
    )

    repo = AsyncMock()
    repo.get_by_authentik_id.return_value = trapped
    repo.update.side_effect = lambda user: user
    svc._repo = repo

    user, is_first_login = await svc.get_or_create_from_jwt(
        {
            "sub": "jwt-sub",
            "email": "platform.admin@iqbalai.dev",
            "role": "platform_admin",
            "tenant_type": "school",
        }
    )

    assert is_first_login is False
    assert user.role == UserRole.PLATFORM_ADMIN
    repo.update.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_or_create_from_jwt_reconciles_district_scope_from_claim() -> None:
    """District admin without district_id gets 403 on /admin/schools; fix on re-login."""
    session = AsyncMock()
    svc = UserService(session)
    unscoped = User(
        id="u-da",
        authentik_id="jwt-sub-da",
        email="district.admin@iqbalai.dev",
        display_name="District Admin",
        role=UserRole.DISTRICT_ADMIN,
        status=UserAccountStatus.ACTIVE,
        district_id=None,
    )

    repo = AsyncMock()
    repo.get_by_authentik_id.return_value = unscoped
    repo.update.side_effect = lambda user: user
    svc._repo = repo

    user, is_first_login = await svc.get_or_create_from_jwt(
        {
            "sub": "jwt-sub-da",
            "email": "district.admin@iqbalai.dev",
            "role": "district_admin",
            "tenant_type": "school",
            "district_id": "00000000-0000-0000-0000-0000000d1571",
            "school_id": None,
        }
    )

    assert is_first_login is False
    assert user.district_id == "00000000-0000-0000-0000-0000000d1571"
    repo.update.assert_awaited_once()
