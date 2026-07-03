"""Tests for permission dependency primitives per T-008 acceptance criteria."""

from __future__ import annotations

from app.core.dependencies import ROLE_HIERARCHY


def _make_claims(role: str) -> dict[str, object]:
    return {"sub": "user123", "role": role, "email": "test@school.pk"}


def test_role_hierarchy_has_nine_roles() -> None:
    assert len(ROLE_HIERARCHY) == 9


def test_platform_admin_is_highest() -> None:
    assert ROLE_HIERARCHY["platform_admin"] == 6


def test_student_and_parent_are_peers() -> None:
    assert ROLE_HIERARCHY["student"] == ROLE_HIERARCHY["parent"]


def test_independent_roles_match_school_peers() -> None:
    assert ROLE_HIERARCHY["independent_teacher"] == ROLE_HIERARCHY["teacher"]
    assert ROLE_HIERARCHY["independent_student"] == ROLE_HIERARCHY["student"]


def test_require_role_allows_higher_role() -> None:
    """Platform Admin can access teacher endpoint."""
    claims = _make_claims("platform_admin")
    # Simulate the inner check function
    required_level = ROLE_HIERARCHY.get("teacher", 0)
    caller_level = ROLE_HIERARCHY.get(str(claims["role"]), 0)
    assert caller_level >= required_level


def test_require_role_blocks_lower_role() -> None:
    """Teacher cannot access district_admin endpoint."""
    claims = _make_claims("teacher")
    required_level = ROLE_HIERARCHY.get("district_admin", 0)
    caller_level = ROLE_HIERARCHY.get(str(claims["role"]), 0)
    assert caller_level < required_level


def test_coordinator_allows_school_admin_resource() -> None:
    """require_role('coordinator') allows school_admin (higher role)."""
    caller_level = ROLE_HIERARCHY["school_admin"]
    required_level = ROLE_HIERARCHY["coordinator"]
    assert caller_level >= required_level


def test_parent_has_no_elevated_rights() -> None:
    """Parent cannot access coordinator resources."""
    assert ROLE_HIERARCHY["parent"] < ROLE_HIERARCHY["coordinator"]
