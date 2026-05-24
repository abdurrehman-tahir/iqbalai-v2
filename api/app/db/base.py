"""SQLAlchemy declarative base + shared mixins."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _uuid7() -> str:
    """Generate a UUIDv7-style ID (time-ordered). Uses uuid4 until uuid7 is in stdlib."""
    # TODO: swap to uuid7 library when ARCH §4.1 guidance is finalised
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""

    pass


class AuditMixin:
    """Adds created_at / updated_at audit timestamps."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class SoftDeleteMixin:
    """Adds deleted_at for soft-delete pattern."""

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


class TenantMixin:
    """Adds tenant_id scoping for multi-tenant records."""

    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
