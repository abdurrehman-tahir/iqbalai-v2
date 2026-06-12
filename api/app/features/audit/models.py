"""AuditLogEntry ORM model — lives in the school schema (T-025).

Intentionally has no AuditMixin or SoftDeleteMixin: audit rows are immutable
by design. No UPDATE/DELETE at the DB level (per ARCH §14.10).
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, _uuid7


class AuditLogEntry(Base):
    """Immutable audit log row.

    Written exclusively via app/infrastructure/audit/log.py.
    Never updated or deleted in application code — DB-level immutability
    enforced via missing UPDATE/DELETE grants (Phase 2 hardening).
    """

    __tablename__ = "audit_log"
    __table_args__ = (
        Index("ix_audit_log_actor_id", "actor_id"),
        Index("ix_audit_log_target_type_target_id", "target_type", "target_id"),
        Index("ix_audit_log_school_id", "school_id"),
        Index("ix_audit_log_created_at", "created_at"),
        {"schema": "school"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    # e.g. "user.created", "tos.published", "syllabus.updated"
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    # NULL when the action is system-initiated (no human actor)
    # VARCHAR(255) — stores Authentik sub claim; matches users.authentik_id width
    actor_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    actor_role: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # e.g. "user", "tos_version", "exam_syllabus"
    target_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    # NULL for platform-level actions that have no school context
    school_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    district_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    # Extra context serialised as JSON string
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Store IPv6 addresses (up to 45 chars: "ffff:ffff:ffff:ffff:ffff:ffff:255.255.255.255")
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    # No updated_at — rows are immutable. created_at is the only timestamp needed.
    # DB-side UTC clock (ARCH §4.3) so rows written via raw SQL still timestamp.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now() AT TIME ZONE 'UTC'"),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        super().__init__(**kwargs)
