"""Grade ORM model — session-scoped grade entity (school schema, T-043)."""

from __future__ import annotations

from enum import StrEnum

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base, SoftDeleteMixin, _uuid7


class GradeStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class Grade(AuditMixin, SoftDeleteMixin, Base):
    """A school-scoped grade pinned to an academic session (ARCH §3.18, flow-2 §3.3)."""

    __tablename__ = "grades"
    __table_args__ = (
        Index(
            "grades_school_name_session_uq",
            "school_id",
            "name",
            "academic_session",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_grades_school_id", "school_id"),
        Index("ix_grades_academic_session", "academic_session"),
        {"schema": "school"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    school_id: Mapped[str] = mapped_column(
        ForeignKey("school.schools.id", ondelete="RESTRICT"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    academic_session: Mapped[str] = mapped_column(String(50), nullable=False)
    level_ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    promoted_from_grade_id: Mapped[str | None] = mapped_column(
        ForeignKey("school.grades.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[GradeStatus] = mapped_column(
        SAEnum(
            GradeStatus,
            name="grades_status_enum",
            schema="school",
            values_callable=lambda e: [m.value for m in e],
            create_type=False,
        ),
        nullable=False,
        default=GradeStatus.ACTIVE,
        server_default=GradeStatus.ACTIVE.value,
    )

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        super().__init__(**kwargs)
