"""Teacher profile ORM model — T-053 (flow-3 §3.1, school tier)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base, SoftDeleteMixin


class TeacherProfile(AuditMixin, SoftDeleteMixin, Base):
    """Extended profile for school-tier teachers (flow-3 §3.1 #16).

    ``profile_completed_at`` is set once mandatory fields are submitted; onboarding
    state derives from this timestamp plus Grade-Subject assignment count.
    """

    __tablename__ = "teacher_profiles"
    __table_args__ = {"schema": "school"}

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("school.users.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    region_province: Mapped[str] = mapped_column(String(100), nullable=False)
    region_district: Mapped[str | None] = mapped_column(String(200), nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    language_preference: Mapped[str] = mapped_column(String(10), nullable=False)
    # Subject catalogue IDs the teacher reports teaching (informational at onboarding).
    subject_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    profile_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )
