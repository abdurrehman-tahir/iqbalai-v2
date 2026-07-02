"""T-091 — Exam Framework data-model tests (offline: metadata + Pydantic shapes).

Acceptance (M-07 T-091):
1. All three tables exist with the status enums + constraints.
2. content_jsonb holds the §3.5.2 structure (topics, weekly_pacing, exam_strategy).
3. Frameworks reachable read-only from independent schema (cross-schema view).
4. target_grade_range + region present for filtering (T-096).
5. A student may have multiple active selections (no unique-per-student constraint).
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import Enum as SAEnum
from sqlalchemy import UniqueConstraint

from app.db.base import Base
from app.features.exam_frameworks import models
from app.features.exam_frameworks.schemas import FrameworkStudyPlanContent

_INDEPENDENT_MIGRATION = (
    Path(__file__).resolve().parents[4]
    / "alembic"
    / "versions"
    / "independent"
    / "0007_exam_framework_views.py"
)


def test_all_three_tables_registered() -> None:
    """Acceptance #1 — the three platform-shared tables exist in the school schema."""
    for name in (
        "school.exam_frameworks",
        "school.framework_study_plans",
        "school.student_framework_selections",
    ):
        assert name in Base.metadata.tables, f"missing table {name}"


def test_framework_status_enum_values() -> None:
    """Acceptance #1 — framework status enum matches the §3.5.1 lifecycle set."""
    col = models.ExamFramework.__table__.columns["status"]
    assert isinstance(col.type, SAEnum)
    assert col.type.native_enum is True
    assert set(col.type.enums) == {
        "draft",
        "researching",
        "pending_approval",
        "published",
        "refreshing",
        "deprecated",
    }


def test_plan_status_enum_includes_approved() -> None:
    """The independent view filters status = 'approved', so it must be a valid value."""
    col = models.FrameworkStudyPlan.__table__.columns["status"]
    assert "approved" in col.type.enums  # type: ignore[attr-defined]


def test_selection_status_and_tenant_type_enums() -> None:
    sel = models.StudentFrameworkSelection.__table__
    assert set(sel.columns["status"].type.enums) == {"active", "abandoned"}  # type: ignore[attr-defined]
    assert set(sel.columns["tenant_type"].type.enums) == {"school", "independent"}  # type: ignore[attr-defined]


def test_region_and_target_grade_range_present() -> None:
    """Acceptance #4 — filtering columns exist on exam_frameworks."""
    cols = models.ExamFramework.__table__.columns
    assert "region" in cols
    assert "target_grade_range" in cols
    # Postgres int[] -> SQLAlchemy ARRAY item type is Integer.
    assert cols["target_grade_range"].type.item_type.__class__.__name__ == "Integer"  # type: ignore[attr-defined]


def test_framework_id_fk_ondelete_choices() -> None:
    """Versions CASCADE with their framework; selections RESTRICT (protect)."""
    plan_fk = next(iter(models.FrameworkStudyPlan.__table__.columns["framework_id"].foreign_keys))
    assert plan_fk.ondelete == "CASCADE"
    sel_fk = next(
        iter(models.StudentFrameworkSelection.__table__.columns["framework_id"].foreign_keys)
    )
    assert sel_fk.ondelete == "RESTRICT"


def test_unique_version_per_framework() -> None:
    """Acceptance #1 — one row per (framework, version)."""
    table = Base.metadata.tables["school.framework_study_plans"]
    uniques = [c for c in table.constraints if isinstance(c, UniqueConstraint)]
    cols = {frozenset(c.columns.keys()) for c in uniques}
    assert frozenset({"framework_id", "version"}) in cols


def test_no_unique_per_student_selection() -> None:
    """Acceptance #5 — a student may hold multiple active selections."""
    table = Base.metadata.tables["school.student_framework_selections"]
    uniques = [c for c in table.constraints if isinstance(c, UniqueConstraint)]
    for c in uniques:
        assert set(c.columns.keys()) != {"student_user_id"}
    # student_user_id is indexed but not unique.
    indexed = {col.name for idx in table.indexes for col in idx.columns}
    assert "student_user_id" in indexed


def test_content_jsonb_shape_roundtrips_section_3_5_2() -> None:
    """Acceptance #2 — §3.5.2 structure validates via the JSONB shape schema."""
    sample = {
        "version": 1,
        "framework_name": "Matric Punjab Board — Physics",
        "region": "Punjab",
        "target_grade_range": [9, 10],
        "sources_cited": [{"url": "https://bise.example/pp", "title": "Past Papers 2020-24"}],
        "generated_at": "2026-07-02T10:00:00Z",
        "topics": [
            {
                "topic_name": "Newton's Laws of Motion",
                "priority_weight": 0.9,
                "exam_frequency": "every_year",
                "recommended_hours": 6,
                "key_concepts": ["inertia", "F=ma"],
                "common_pitfalls": ["sign errors"],
                "past_paper_patterns": "MCQs typically test the third law.",
                "practice_problems_generated": ["A 2kg block ..."],
                "expert_tips": ["Draw the free-body diagram first."],
            }
        ],
        "weekly_pacing": [
            {"week_from_exam": 12, "focus_topics": ["Newton's Laws"], "hours_estimated": 10}
        ],
        "exam_strategy": {
            "time_allocation": "1 min per MCQ",
            "scoring_strategy": "Attempt all MCQs.",
            "common_mistakes": ["leaving MCQs blank"],
        },
    }
    parsed = FrameworkStudyPlanContent.model_validate(sample)
    assert parsed.topics[0].priority_weight == 0.9
    assert parsed.weekly_pacing[0].week_from_exam == 12
    assert parsed.exam_strategy.time_allocation == "1 min per MCQ"


def test_independent_cross_schema_views_defined() -> None:
    """Acceptance #3 — the independent schema gets read-only published/approved views."""
    text = _INDEPENDENT_MIGRATION.read_text()
    assert "CREATE VIEW independent.exam_frameworks" in text
    assert "WHERE status = 'published'" in text
    assert "CREATE VIEW independent.framework_study_plans" in text
    assert "WHERE status = 'approved'" in text
