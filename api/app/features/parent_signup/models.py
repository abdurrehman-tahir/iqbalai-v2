"""Parent profile ORM model — T-080."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base, SoftDeleteMixin


class ParentProfile(AuditMixin, SoftDeleteMixin, Base):
    """Extended profile for school-tier parents (flow-4 §3.3)."""

    __tablename__ = "parent_profiles"
    __table_args__ = {"schema": "school"}

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("school.users.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    language_preference: Mapped[str] = mapped_column(String(10), nullable=False)
    is_email_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    unlinked_since: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    def __init__(self, **kwargs: object) -> None:
        if "is_email_verified" not in kwargs:
            kwargs["is_email_verified"] = False
        super().__init__(**kwargs)
