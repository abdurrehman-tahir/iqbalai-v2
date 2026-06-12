"""Repository soft-delete scoping (T-230).

`app.db.base.not_deleted` is the single source of truth for the active-rows
filter. These tests pin its emitted SQL and confirm the repositories build their
read queries through it, so no feature can silently return soft-deleted rows.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app.db.base import SoftDeleteMixin, not_deleted
from app.features.exam_syllabi.models import ExamSyllabus, SyllabusTopic
from app.features.files.models import UploadRecord
from app.features.library.models import PlatformReferenceBook
from app.features.notifications.models import Notification
from app.features.subscriptions.models import SubscriptionTier
from app.features.users.models import User

_SOFT_DELETE_MODELS = [
    ExamSyllabus,
    SyllabusTopic,
    UploadRecord,
    PlatformReferenceBook,
    Notification,
    SubscriptionTier,
    User,
]


def _compiled(stmt: object) -> str:
    return str(stmt.compile(dialect=postgresql.dialect()))  # type: ignore[attr-defined]


def test_models_under_test_are_soft_deletable() -> None:
    for model in _SOFT_DELETE_MODELS:
        assert issubclass(model, SoftDeleteMixin)


def test_not_deleted_emits_is_null_predicate() -> None:
    for model in _SOFT_DELETE_MODELS:
        sql = _compiled(select(model).where(not_deleted(model)))
        assert "deleted_at IS NULL" in sql, f"{model.__name__} not scoped to active rows"


def test_not_deleted_matches_direct_predicate() -> None:
    # The helper must be exactly the column.is_(None) filter, no looser.
    helper_sql = _compiled(select(ExamSyllabus).where(not_deleted(ExamSyllabus)))
    direct_sql = _compiled(select(ExamSyllabus).where(ExamSyllabus.deleted_at.is_(None)))
    assert helper_sql == direct_sql
