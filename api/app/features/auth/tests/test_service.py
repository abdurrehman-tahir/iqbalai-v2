"""Tests for AuthService.get_post_login_path — T-244.

MUST stay in sync with frontend/src/lib/auth.ts's ALL_ROLES / getPostLoginPath
(T-239) — same 9-role set, same paths.
"""

from __future__ import annotations

import pytest

from app.features.auth.service import get_post_login_path

# Mirrors frontend/src/lib/auth.ts's ALL_ROLES exactly.
ALL_ROLES = (
    "platform_admin",
    "district_admin",
    "school_admin",
    "coordinator",
    "teacher",
    "student",
    "parent",
    "independent_teacher",
    "independent_student",
)

EXPECTED_DASHBOARD = {
    "platform_admin": "/admin",
    "district_admin": "/admin/district/schools",
    "school_admin": "/school/admin",
    "coordinator": "/coordinator",
    "teacher": "/teacher",
    "student": "/student",
    "parent": "/parent",
    "independent_teacher": "/independent/teacher",
    "independent_student": "/independent/student",
}


def test_covers_every_role_in_the_union() -> None:
    assert set(ALL_ROLES) == set(EXPECTED_DASHBOARD)


@pytest.mark.parametrize("role", ALL_ROLES)
def test_routes_each_role_to_its_documented_dashboard(role: str) -> None:
    assert get_post_login_path(role) == EXPECTED_DASHBOARD[role]


def test_unhandled_role_raises_instead_of_silently_defaulting() -> None:
    with pytest.raises(ValueError, match="unhandled role"):
        get_post_login_path("not_a_real_role")
