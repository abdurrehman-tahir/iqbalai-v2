"""Independent user ORM model — lives in the independent schema per ARCH §3.16."""

from __future__ import annotations

import enum

from sqlalchemy import Enum as SAEnum
from sqlalchemy import Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base, SoftDeleteMixin, _uuid7


class IndependentUserRole(str, enum.Enum):
    """Roles for self-signup independent users."""

    INDEPENDENT_TEACHER = "independent_teacher"
    INDEPENDENT_STUDENT = "independent_student"


class IndependentUserAccountStatus(str, enum.Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DEACTIVATED = "deactivated"


class IndependentUser(AuditMixin, SoftDeleteMixin, Base):
    """User table in the independent schema — no school/district context."""

    __tablename__ = "users"
    __table_args__ = (
        Index("ix_independent_users_authentik_id", "authentik_id", unique=True),
        Index("ix_independent_users_email", "email"),
        {"schema": "independent"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    authentik_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[IndependentUserRole] = mapped_column(
        SAEnum(
            IndependentUserRole,
            name="independentuserrole",
            schema="independent",
            values_callable=lambda roles: [r.value for r in roles],
            native_enum=True,
            create_type=False,
        ),
        nullable=False,
    )
    status: Mapped[IndependentUserAccountStatus] = mapped_column(
        SAEnum(
            IndependentUserAccountStatus,
            name="independentuseraccountstatus",
            schema="independent",
            values_callable=lambda statuses: [s.value for s in statuses],
            native_enum=True,
            create_type=False,
        ),
        nullable=False,
        default=IndependentUserAccountStatus.ACTIVE,
    )
    language_preference: Mapped[str] = mapped_column(String(10), nullable=False, default="en")

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        super().__init__(**kwargs)
