"""SQLAlchemy declarative base + shared mixins."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import ColumnElement, DateTime, String, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# DB-side UTC clock for audit timestamps (ARCH §4.3): the DB sets created_at /
# updated_at so rows inserted outside the ORM (raw SQL, seeds, data migrations)
# still get correct values. The Python-side default/onupdate below is kept only
# so in-memory ORM instances are populated before flush (unit tests, returns).
_UTC_NOW = text("now() AT TIME ZONE 'UTC'")


def _uuid7() -> str:
    """Generate a UUIDv7-style ID (time-ordered). Uses uuid4 until uuid7 is in stdlib."""
    # DEFERRED (T-230 audit, AUDIT_LOG.md): ARCH §4.2 locks native UUIDv7 (uuid_utils)
    # + an IdMixin. Swapping String(36)→native UUID ripples through every FK column,
    # the seed, repos, and tests, and is best done when schools/districts land (M-02).
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""

    pass


class AuditMixin:
    """Adds created_at / updated_at audit timestamps (ARCH §4.3, DB-set, UTC)."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=_UTC_NOW,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=_UTC_NOW,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class SoftDeleteMixin:
    """Adds deleted_at for soft-delete pattern (ARCH §4.4, indexed)."""

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        index=True,
    )

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


def not_deleted(model: type[SoftDeleteMixin]) -> ColumnElement[bool]:
    """Soft-delete scoping predicate: ``model.deleted_at IS NULL`` (ARCH §4.4).

    Single source of truth for the active-rows filter so every repository scopes
    out soft-deleted rows identically. Use in a query via
    ``select(Model).where(not_deleted(Model))``.
    """
    return model.deleted_at.is_(None)


class TenantMixin:
    """Adds tenant_id scoping for multi-tenant records."""

    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
