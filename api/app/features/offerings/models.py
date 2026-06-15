"""GradeSubjectOffering ORM model — school schema (T-045)."""

from __future__ import annotations

from enum import StrEnum

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base, SoftDeleteMixin, _uuid7


class OfferingStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class GradeSubjectOffering(AuditMixin, SoftDeleteMixin, Base):
    """Links a subject catalogue entry to a grade for an academic session."""

    __tablename__ = "grade_subject_offerings"
    __table_args__ = (
        Index(
            "grade_subject_offerings_grade_subject_uq",
            "grade_id",
            "subject_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_grade_subject_offerings_school_id", "school_id"),
        Index("ix_grade_subject_offerings_grade_id", "grade_id"),
        Index("ix_grade_subject_offerings_subject_id", "subject_id"),
        Index("ix_grade_subject_offerings_assigned_teacher_id", "assigned_teacher_id"),
        {"schema": "school"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    school_id: Mapped[str] = mapped_column(
        ForeignKey("school.schools.id", ondelete="RESTRICT"),
        nullable=False,
    )
    grade_id: Mapped[str] = mapped_column(
        ForeignKey("school.grades.id", ondelete="RESTRICT"),
        nullable=False,
    )
    subject_id: Mapped[str] = mapped_column(
        ForeignKey("school.subjects.id", ondelete="RESTRICT"),
        nullable=False,
    )
    assigned_teacher_id: Mapped[str | None] = mapped_column(
        ForeignKey("school.users.id", ondelete="SET NULL"),
        nullable=True,
    )
    academic_session: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[OfferingStatus] = mapped_column(
        SAEnum(
            OfferingStatus,
            name="grade_subject_offerings_status_enum",
            schema="school",
            values_callable=lambda e: [m.value for m in e],
            create_type=False,
        ),
        nullable=False,
        default=OfferingStatus.ACTIVE,
        server_default=OfferingStatus.ACTIVE.value,
    )

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        super().__init__(**kwargs)
