"""Tests for JWT role claim parsing."""

from __future__ import annotations

from app.features.users.models import UserRole
from app.features.users.service import parse_user_role


def test_parse_user_role_accepts_value() -> None:
    assert parse_user_role("platform_admin") is UserRole.PLATFORM_ADMIN


def test_parse_user_role_accepts_enum_name() -> None:
    assert parse_user_role("STUDENT") is UserRole.STUDENT


def test_parse_user_role_defaults_to_student() -> None:
    assert parse_user_role(None) is UserRole.STUDENT
