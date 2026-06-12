"""User ORM model — lives in the school schema."""

from __future__ import annotations

import enum

from sqlalchemy import Enum as SAEnum
from sqlalchemy import Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base, SoftDeleteMixin, _uuid7


class UserRole(str, enum.Enum):
    """Six-level role hierarchy per ARCH §6.7."""

    PLATFORM_ADMIN = "platform_admin"
    DISTRICT_ADMIN = "district_admin"
    SCHOOL_ADMIN = "school_admin"
    COORDINATOR = "coordinator"
    TEACHER = "teacher"
    STUDENT = "student"
    PARENT = "parent"


class UserAccountStatus(str, enum.Enum):
    """User lifecycle status per flow-2 §3.5."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    DEACTIVATED = "deactivated"


class User(AuditMixin, SoftDeleteMixin, Base):
    """User table in the school schema per ARCH §6.2 + §4.1."""

    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_authentik_id", "authentik_id", unique=True),
        Index("ix_users_email", "email"),
        Index("ix_users_school_id", "school_id"),
        Index("ix_users_district_id", "district_id"),
        {"schema": "school"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    authentik_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
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
    status: Mapped[UserAccountStatus] = mapped_column(
        SAEnum(
            UserAccountStatus,
            name="useraccountstatus",
            schema="school",
            values_callable=lambda statuses: [s.value for s in statuses],
            native_enum=True,
            create_type=False,
        ),
        nullable=False,
        default=UserAccountStatus.ACTIVE,
    )
    school_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    district_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    # Scoped IDs: comma-separated list of IDs the user is scoped to (e.g., class IDs for teacher)
    scoped_ids: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        super().__init__(**kwargs)
