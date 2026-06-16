"""Shared grade-scope helpers for M-03 structure endpoints."""

from __future__ import annotations

import re

from app.core.dependencies import ROLE_HIERARCHY
from app.core.exceptions import PermissionDeniedError, ValidationError
from app.features.grades.cross_grade import (
    assert_cross_grade_access,
    assert_cross_grade_access_by_ordinal,
    library_item_visible_for_grade_context,
)
from app.features.users.models import User

__all__ = [
    "assert_cross_grade_access",
    "assert_cross_grade_access_by_ordinal",
    "assert_grade_in_scope",
    "derive_level_ordinal",
    "library_item_visible_for_grade_context",
    "parse_grade_scope",
]


def parse_grade_scope(scoped_ids: str | None) -> set[str]:
    if not scoped_ids:
        return set()
    return {part.strip() for part in scoped_ids.split(",") if part.strip()}


def derive_level_ordinal(name: str) -> int:
    """Parse a numeric year-level from a grade name (e.g. 'Grade 9' -> 9)."""
    match = re.search(r"\d+", name)
    if not match:
        raise ValidationError(f"Cannot derive level ordinal from grade name '{name}'")
    return int(match.group())


def assert_grade_in_scope(actor: User, grade_name: str) -> None:
    """Coordinators may only act on grades within their scoped_ids; admins bypass."""
    caller_level = ROLE_HIERARCHY.get(actor.role.value, 0)
    if caller_level >= ROLE_HIERARCHY["school_admin"]:
        return
    scope = parse_grade_scope(actor.scoped_ids)
    if grade_name not in scope:
        raise PermissionDeniedError(f"Grade '{grade_name}' is outside your assigned scope")
