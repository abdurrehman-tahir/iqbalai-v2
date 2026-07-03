"""Independent teacher profile ORM model — M-05 T-070."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base, SoftDeleteMixin


class IndependentTeacherProfile(AuditMixin, SoftDeleteMixin, Base):
    """Minimal profile for independent teachers (flow-3 §3.2)."""

    __tablename__ = "independent_teacher_profiles"
    __table_args__ = {"schema": "independent"}

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("independent.users.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    language_preference: Mapped[str] = mapped_column(String(10), nullable=False)
    profile_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )
