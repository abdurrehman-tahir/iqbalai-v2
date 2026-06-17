"""Cross-grade unidirectional access rule — T-047."""

from __future__ import annotations

from app.core.exceptions import PermissionDeniedError
from app.features.grades.models import Grade


def assert_cross_grade_access(source_grade: Grade, target_grade: Grade) -> None:
    """A grade may access material only from grades at or below its level (ARCH §3.18)."""
    if source_grade.level_ordinal < target_grade.level_ordinal:
        raise PermissionDeniedError(
            f"Grade '{source_grade.name}' cannot access material from higher grade "
            f"'{target_grade.name}'"
        )
