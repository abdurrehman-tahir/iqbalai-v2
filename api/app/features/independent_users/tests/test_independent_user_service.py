"""Tests for independent user JWT upsert."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.features.independent_users.models import IndependentUserRole
from app.features.independent_users.service import IndependentUserService, parse_independent_user_role


def test_parse_independent_user_role() -> None:
    assert parse_independent_user_role("independent_teacher") == IndependentUserRole.INDEPENDENT_TEACHER
    assert parse_independent_user_role("INDEPENDENT_STUDENT") == IndependentUserRole.INDEPENDENT_STUDENT


@pytest.mark.asyncio
async def test_get_or_create_from_jwt_creates_new_user() -> None:
    repo = MagicMock()
    repo.get_by_authentik_id = AsyncMock(return_value=None)
    repo.get_by_email = AsyncMock(return_value=None)
    repo.create = AsyncMock(side_effect=lambda u: u)

    svc = IndependentUserService(MagicMock())
    svc._repo = repo

    user, is_first = await svc.get_or_create_from_jwt(
        {
            "sub": "auth-123",
            "email": "new@example.com",
            "name": "New User",
            "role": "independent_teacher",
        }
    )
    assert is_first is True
    assert user.role == IndependentUserRole.INDEPENDENT_TEACHER
    assert user.email == "new@example.com"
    repo.create.assert_awaited_once()
