"""T-209 — self-study data-model tests (offline: metadata + migrations)."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from sqlalchemy import Table
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

from app.db.base import Base
from app.features.self_study import models as self_study_models
from app.features.self_study.models import (
    IndependentReminderPreference,
    IndependentStudentGoal,
    IndependentStudentMaterial,
    IndependentUserSettings,
    MaterialSourceType,
    SchoolReminderPreference,
    SchoolStudentGoal,
    SchoolStudentMaterial,
    SchoolStudyPlan,
    StudyPlanStatus,
)
from app.features.self_study.subscription_gate import check_self_study_subscription_limits

_ROOT = Path(__file__).resolve().parents[4]
_SCHOOL_MIGRATION = _ROOT / "alembic" / "versions" / "school" / "0081_self_study.py"
_IND_MIGRATION = _ROOT / "alembic" / "versions" / "independent" / "0021_self_study.py"

_TABLES = (
    "student_materials",
    "student_goals",
    "prep_book_topics",
    "study_plans",
    "study_plan_items",
    "study_plan_days",
    "reminder_preferences",
)


def test_all_tables_both_schemas() -> None:
    """Acceptance #1 — §10 tables in school + independent."""
    assert self_study_models is not None
    for name in _TABLES:
        assert f"school.{name}" in Base.metadata.tables, f"missing school.{name}"
        assert f"independent.{name}" in Base.metadata.tables, f"missing independent.{name}"
    assert "independent.user_settings" in Base.metadata.tables
    # Privacy #72 reuses school.user_settings — no duplicate table.
    assert "school.student_self_study_privacy" not in Base.metadata.tables
    assert "independent.student_self_study_privacy" not in Base.metadata.tables


def test_school_migration_revises_0080() -> None:
    assert _SCHOOL_MIGRATION.is_file()
    text = _SCHOOL_MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "school_0081"' in text
    assert 'down_revision: str = "school_0080"' in text
    for name in _TABLES:
        assert name in text


def test_independent_migration_revises_0020() -> None:
    assert _IND_MIGRATION.is_file()
    text = _IND_MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "independent_0021"' in text
    assert 'down_revision: str = "independent_0020"' in text
    assert "user_settings" in text
    for name in _TABLES:
        assert name in text


def test_study_plans_strong_topics_is_array() -> None:
    col = cast(Table, SchoolStudyPlan.__table__).columns["strong_topics"]
    assert isinstance(col.type, ARRAY)
    plan = SchoolStudyPlan(student_user_id="u1", strong_topics=["optics"])
    assert plan.strong_topics == ["optics"]
    assert plan.status == StudyPlanStatus.ACTIVE
    assert plan.subscription_tier_id is None  # gate hook present, unset


def test_material_defaults() -> None:
    m = SchoolStudentMaterial(
        student_user_id="u1",
        title="Prep book",
        source_type=MaterialSourceType.PDF,
    )
    assert m.added_to_library is False
    assert m.book_type is None
    ind = IndependentStudentMaterial(
        student_user_id="u2",
        title="Typed notes",
        source_type=MaterialSourceType.TYPED,
    )
    assert ind.tenant_type.value == "independent"


def test_goal_and_reminder_shapes() -> None:
    from datetime import date

    g = SchoolStudentGoal(
        student_user_id="u1",
        goal_date=date(2026, 10, 15),
        goal_text="Finish chapter 3",
    )
    assert g.achieved is None
    r = SchoolReminderPreference(student_user_id="u1")
    assert r.timezone == "Asia/Karachi"
    assert r.push_enabled is True
    ir = IndependentReminderPreference(student_user_id="u2")
    assert ir.sms_enabled is False
    ig = IndependentStudentGoal(
        student_user_id="u2",
        goal_date=date(2026, 10, 15),
        goal_text="Review",
    )
    assert ig.tenant_type.value == "independent"


def test_independent_user_settings_mode_state_jsonb() -> None:
    col = cast(Table, IndependentUserSettings.__table__).columns["mode_state_jsonb"]
    assert isinstance(col.type, JSONB)
    s = IndependentUserSettings(user_id="u1")
    assert s.active_mode == "self_study"
    assert s.mode_state_jsonb == {"self_study": {}}


def test_subscription_gate_noop_when_limits_unset() -> None:
    """Acceptance #5."""
    result = check_self_study_subscription_limits(
        active_plan_count=99,
        monthly_upload_count=99,
    )
    assert result.enforced is False
    assert result.allowed is True
    assert result.limits.max_active_plans is None
