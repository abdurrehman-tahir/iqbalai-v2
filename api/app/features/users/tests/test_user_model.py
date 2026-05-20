"""Tests for User model basics."""
from __future__ import annotations

import pytest

from app.features.users.models import User, UserRole


def test_user_role_hierarchy_values() -> None:
    """Verify role enum has all 7 roles."""
    roles = {r.value for r in UserRole}
    assert "platform_admin" in roles
    assert "student" in roles
    assert "parent" in roles
    assert len(roles) == 7


def test_user_defaults() -> None:
    """User ID is auto-generated."""
    user = User(
        authentik_id="auth|123",
        email="test@school.pk",
        display_name="Test User",
        role=UserRole.STUDENT,
    )
    assert user.id is not None
    assert len(user.id) == 36  # UUID format
    assert user.deleted_at is None
    assert user.is_deleted is False
