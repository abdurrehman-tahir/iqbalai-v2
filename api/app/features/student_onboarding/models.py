"""School student profile ORM model — T-078."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base, SoftDeleteMixin


class StudentProfile(AuditMixin, SoftDeleteMixin, Base):
    """Extended profile for school-tier students (flow-4 §3.1)."""

    __tablename__ = "student_profiles"
    __table_args__ = {"schema": "school"}

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("school.users.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    language_preference: Mapped[str] = mapped_column(String(10), nullable=False)
    tos_accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    profile_basic_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    lecture_mode_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    self_study_mode_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    deferrable_banner_dismissed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    exam_date: Mapped[date | None] = mapped_column(Date, nullable=True, default=None)
    exam_countdown_sent_days: Mapped[str | None] = mapped_column(
        String(32), nullable=True, default=None
    )
    is_graduated: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    graduated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    migrated_out: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    migrated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    migration_reminder_sent_days: Mapped[str | None] = mapped_column(
        String(32), nullable=True, default=None
    )

    def __init__(self, **kwargs: object) -> None:
        if "lecture_mode_enabled" not in kwargs:
            kwargs["lecture_mode_enabled"] = False
        if "self_study_mode_enabled" not in kwargs:
            kwargs["self_study_mode_enabled"] = False
        if "deferrable_banner_dismissed" not in kwargs:
            kwargs["deferrable_banner_dismissed"] = False
        if "is_graduated" not in kwargs:
            kwargs["is_graduated"] = False
        if "migrated_out" not in kwargs:
            kwargs["migrated_out"] = False
        super().__init__(**kwargs)
