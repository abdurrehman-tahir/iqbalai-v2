"""Unit tests for cross-grade access rule — T-047."""

from __future__ import annotations

import pytest

from app.core.exceptions import PermissionDeniedError
from app.features.grades.cross_grade import assert_cross_grade_access
from app.features.grades.models import Grade, GradeStatus


def _grade(name: str, level: int) -> Grade:
    return Grade(
        id=f"g-{level}",
        school_id="school-1",
        name=name,
        academic_session="2025-2026",
        level_ordinal=level,
        status=GradeStatus.ACTIVE,
    )


def test_grade_10_accesses_grade_9() -> None:
    assert_cross_grade_access(_grade("Grade 10", 10), _grade("Grade 9", 9))


def test_grade_9_accesses_grade_9() -> None:
    assert_cross_grade_access(_grade("Grade 9", 9), _grade("Grade 9", 9))


def test_grade_9_cannot_access_grade_10() -> None:
    with pytest.raises(PermissionDeniedError):
        assert_cross_grade_access(_grade("Grade 9", 9), _grade("Grade 10", 10))


@pytest.mark.parametrize(
    ("source_level", "target_level", "allowed"),
    [
        (12, 9, True),
        (11, 11, True),
        (10, 11, False),
        (8, 10, False),
        (9, 8, True),
    ],
)
def test_cross_grade_matrix(source_level: int, target_level: int, allowed: bool) -> None:
    source = _grade(f"Grade {source_level}", source_level)
    target = _grade(f"Grade {target_level}", target_level)
    if allowed:
        assert_cross_grade_access(source, target)
    else:
        with pytest.raises(PermissionDeniedError):
            assert_cross_grade_access(source, target)
