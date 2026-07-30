"""Independent student profile ORM model — M-05 T-071."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base, SoftDeleteMixin


class IndependentStudentProfile(AuditMixin, SoftDeleteMixin, Base):
    """Profile for independent students (flow-4 §3.2)."""

    __tablename__ = "independent_student_profiles"
    __table_args__ = {"schema": "independent"}

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("independent.users.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    language_preference: Mapped[str] = mapped_column(String(10), nullable=False)
    grade_level: Mapped[int] = mapped_column(Integer, nullable=False)
    exam_syllabus_id: Mapped[str] = mapped_column(String(36), nullable=False)
    exam_date: Mapped[date | None] = mapped_column(Date, nullable=True, default=None)
    # Comma-separated countdown day markers + optional "passed" (T-107), mirrors school.
    exam_countdown_sent_days: Mapped[str | None] = mapped_column(String(32), nullable=True)
    profile_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )
