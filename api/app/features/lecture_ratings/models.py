"""Lecture rating ORM model — T-192 (flow-6 §3.11 / §10).

One optional 1–5 rating per (lecture, student), editable (upsert). Ratings are
coaching signal for the teacher, never grading: they are only ever exposed as
an anonymous aggregate and never feed any student-facing ranking.
"""

from __future__ import annotations

from enum import StrEnum

from sqlalchemy import CheckConstraint, ForeignKey, Index, SmallInteger, String, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base, _uuid7


class RatingTenantType(StrEnum):
    SCHOOL = "school"
    INDEPENDENT = "independent"


def _tenant_type_enum(schema: str) -> SAEnum:
    # Reuse lectures_tenant_type_enum created by school_0051.
    return SAEnum(
        RatingTenantType,
        name="lectures_tenant_type_enum",
        schema=schema,
        values_callable=lambda items: [item.value for item in items],
        native_enum=True,
        create_type=False,
    )


class SchoolLectureRating(AuditMixin, Base):
    __tablename__ = "lecture_ratings"
    __table_args__ = (
        UniqueConstraint(
            "lecture_id", "student_user_id", name="lecture_ratings_lecture_student_uq"
        ),
        CheckConstraint("rating BETWEEN 1 AND 5", name="lecture_ratings_value_check"),
        Index("ix_lecture_ratings_lecture_id", "lecture_id"),
        Index("ix_lecture_ratings_student_user_id", "student_user_id"),
        Index("ix_lecture_ratings_lecture_version_id", "lecture_version_id"),
        {"schema": "school"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    # CASCADE: ARCH §4.6 locks lectures → lecture_ratings CASCADE.
    lecture_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("school.lectures.id", ondelete="CASCADE"), nullable=False
    )
    student_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("school.users.id", ondelete="CASCADE"), nullable=False
    )
    # Version that was on screen when rated (provenance; immutable versions).
    lecture_version_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("school.lecture_versions.id", ondelete="SET NULL"), nullable=True
    )
    rating: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    tenant_type: Mapped[RatingTenantType] = mapped_column(
        _tenant_type_enum("school"), nullable=False, default=RatingTenantType.SCHOOL
    )

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        if "tenant_type" not in kwargs:
            kwargs["tenant_type"] = RatingTenantType.SCHOOL
        super().__init__(**kwargs)
