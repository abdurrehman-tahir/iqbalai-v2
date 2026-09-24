"""T-151 — lecture_sessions model + migration shape tests (offline)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import Enum as SAEnum
from sqlalchemy import Table

from app.db.base import Base, SoftDeleteMixin
from app.features.lectures.models import (
    LectureSessionMode,
    LectureSessionStatus,
    LectureTenantType,
    SchoolLectureSession,
)

_SCHOOL_MIGRATION = (
    Path(__file__).resolve().parents[4]
    / "alembic"
    / "versions"
    / "school"
    / "0066_lecture_sessions.py"
)


def test_lecture_sessions_table_registered_school_only() -> None:
    assert "school.lecture_sessions" in Base.metadata.tables
    assert "independent.lecture_sessions" not in Base.metadata.tables


def test_lecture_session_has_no_soft_delete() -> None:
    assert not issubclass(SchoolLectureSession, SoftDeleteMixin)


def test_lecture_session_columns_and_enums() -> None:
    table = Base.metadata.tables["school.lecture_sessions"]
    assert isinstance(table, Table)
    cols = {c.name for c in table.columns}
    assert {
        "id",
        "lecture_id",
        "student_user_id",
        "tenant_type",
        "mode",
        "status",
        "opened_at",
        "last_activity_at",
        "ended_at",
        "created_at",
        "updated_at",
    } <= cols

    mode_col = table.c.mode.type
    status_col = table.c.status.type
    assert isinstance(mode_col, SAEnum)
    assert isinstance(status_col, SAEnum)
    assert set(mode_col.enums) == {m.value for m in LectureSessionMode}
    assert set(status_col.enums) == {s.value for s in LectureSessionStatus}


def test_lecture_session_defaults() -> None:
    now = datetime.now(timezone.utc)
    row = SchoolLectureSession(
        lecture_id="lec-1",
        student_user_id="stu-1",
        opened_at=now,
        last_activity_at=now,
    )
    assert row.tenant_type == LectureTenantType.SCHOOL
    assert row.mode == LectureSessionMode.TEXT
    assert row.status == LectureSessionStatus.ACTIVE
    assert row.ended_at is None
    assert row.id


def test_migration_file_exists_and_revises_quizzes() -> None:
    text = _SCHOOL_MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "school_0066"' in text
    assert 'down_revision: str = "school_0065"' in text
    assert "lecture_sessions" in text
    assert "self_study_sessions" in text  # docstring notes Flow 8 deferral
