"""ParentChildLink ORM model — T-081 / ARCH §6.13."""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base, SoftDeleteMixin, _uuid7


class ParentChildLinkStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REVOKED = "revoked"


class ParentChildLink(AuditMixin, SoftDeleteMixin, Base):
    """Opt-in link between a parent and a school student."""

    __tablename__ = "parent_child_links"
    __table_args__ = (
        UniqueConstraint(
            "parent_user_id",
            "student_user_id",
            name="uq_parent_child_links_parent_student",
        ),
        {"schema": "school"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    parent_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("school.users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    student_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("school.users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status: Mapped[ParentChildLinkStatus] = mapped_column(
        SAEnum(
            ParentChildLinkStatus,
            name="parent_child_link_status",
            schema="school",
            values_callable=lambda statuses: [s.value for s in statuses],
            native_enum=True,
            create_type=False,
        ),
        nullable=False,
        default=ParentChildLinkStatus.PENDING,
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    rejected_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        if "rejected_count" not in kwargs:
            kwargs["rejected_count"] = 0
        super().__init__(**kwargs)
