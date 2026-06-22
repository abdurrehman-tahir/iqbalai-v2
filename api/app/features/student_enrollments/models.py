"""Student enrollment ORM model — school schema (T-077)."""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base, SoftDeleteMixin, _uuid7


class StudentEnrollmentStatus(str, enum.Enum):
    """Lifecycle status for a student's grade-section enrollment."""

    ACTIVE = "active"
    WITHDRAWN = "withdrawn"
    GRADUATED = "graduated"


class StudentEnrollment(AuditMixin, SoftDeleteMixin, Base):
    """Coordinator enrollment of a school student into a Grade + Section."""

    __tablename__ = "student_enrollments"
    __table_args__ = {"schema": "school"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    school_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("school.schools.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    student_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("school.users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    grade_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("school.grades.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    section_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("school.sections.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    academic_session: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[StudentEnrollmentStatus] = mapped_column(
        SAEnum(
            StudentEnrollmentStatus,
            name="student_enrollment_status",
            schema="school",
            values_callable=lambda statuses: [s.value for s in statuses],
            native_enum=True,
            create_type=False,
        ),
        nullable=False,
        default=StudentEnrollmentStatus.ACTIVE,
    )
    enrolled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        if "status" not in kwargs:
            kwargs["status"] = StudentEnrollmentStatus.ACTIVE
        super().__init__(**kwargs)
