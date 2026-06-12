"""User invite ORM model — Path A admin invitation flow (T-030)."""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base, _uuid7
from app.features.users.models import UserRole


class UserInviteStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    EXPIRED = "expired"
    REJECTED = "rejected"
    LOCKED = "locked"


class UserInvite(AuditMixin, Base):
    """Pending or completed admin invitation."""

    __tablename__ = "user_invites"
    __table_args__ = {"schema": "school"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    invited_by_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    invited_role: Mapped[UserRole] = mapped_column(
        SAEnum(
            UserRole,
            name="userrole",
            schema="school",
            values_callable=lambda roles: [r.value for r in roles],
            native_enum=True,
            create_type=False,
        ),
        nullable=False,
    )
    district_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("school.districts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    school_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("school.schools.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    scope_ids_json: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    authentik_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[UserInviteStatus] = mapped_column(
        SAEnum(
            UserInviteStatus,
            name="user_invite_status",
            schema="school",
            values_callable=lambda statuses: [s.value for s in statuses],
            native_enum=True,
            create_type=False,
        ),
        nullable=False,
        default=UserInviteStatus.PENDING,
    )
    resent_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rejected_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        if "resent_count" not in kwargs:
            kwargs["resent_count"] = 0
        if "rejected_count" not in kwargs:
            kwargs["rejected_count"] = 0
        if "status" not in kwargs:
            kwargs["status"] = UserInviteStatus.PENDING
        super().__init__(**kwargs)
