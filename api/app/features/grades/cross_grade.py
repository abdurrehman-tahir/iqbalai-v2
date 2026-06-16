"""Cross-grade unidirectional access rule — T-047."""

from __future__ import annotations

from app.core.exceptions import PermissionDeniedError
from app.features.grades.models import Grade, GradeStatus


def assert_cross_grade_access(source_grade: Grade, target_grade: Grade) -> None:
    """A grade may access material only from grades at or below its level (ARCH §3.18)."""
    if source_grade.level_ordinal < target_grade.level_ordinal:
        raise PermissionDeniedError(
            f"Grade '{source_grade.name}' cannot access material from higher grade "
            f"'{target_grade.name}'"
        )


def assert_cross_grade_access_by_ordinal(source_ordinal: int, target_ordinal: int) -> None:
    """Apply ``assert_cross_grade_access`` using level ordinals (library visibility, etc.)."""
    source = Grade(
        id=f"ordinal-{source_ordinal}",
        school_id="",
        name=f"Grade {source_ordinal}",
        academic_session="",
        level_ordinal=source_ordinal,
        status=GradeStatus.ACTIVE,
    )
    target = Grade(
        id=f"ordinal-{target_ordinal}",
        school_id="",
        name=f"Grade {target_ordinal}",
        academic_session="",
        level_ordinal=target_ordinal,
        status=GradeStatus.ACTIVE,
    )
    assert_cross_grade_access(source, target)


def library_item_visible_for_grade_context(
    *,
    context_ordinal: int,
    item_grade_ordinal: int | None,
) -> bool:
    """Return whether a library item is visible in a grade context (untagged always visible)."""
    if item_grade_ordinal is None:
        return True
    try:
        assert_cross_grade_access_by_ordinal(context_ordinal, item_grade_ordinal)
    except PermissionDeniedError:
        return False
    return True
