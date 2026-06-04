"""ORM models for ToS versions, Disclaimer versions, and user acceptances."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base, _uuid7


class TosVersion(AuditMixin, Base):
    """Immutable ToS version record. New publish = new row, never UPDATE.

    Platform-wide (no school_id) — accessible across tenants via cross-schema
    views per ARCH §3.16.
    """

    __tablename__ = "tos_versions"
    __table_args__ = ({"schema": "school"},)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content_md: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="en")
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # VARCHAR(255) — matches users.authentik_id; Authentik sub claim can exceed 36 chars
    published_by: Mapped[str | None] = mapped_column(String(255), nullable=True)

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        super().__init__(**kwargs)


class DisclaimerVersion(AuditMixin, Base):
    """Immutable Disclaimer version record. 500-char limit enforced at service layer.

    Shown inline next to AI-generated prediction surfaces per Flow 1 §3.6.
    """

    __tablename__ = "disclaimer_versions"
    __table_args__ = ({"schema": "school"},)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(String(500), nullable=False)
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="en")
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # VARCHAR(255) — matches users.authentik_id; Authentik sub claim can exceed 36 chars
    published_by: Mapped[str | None] = mapped_column(String(255), nullable=True)

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        super().__init__(**kwargs)


class UserTosAcceptance(AuditMixin, Base):
    """Records that a user accepted a specific ToS version.

    One row per (user_id, tos_version_id) — unique constraint enforced.
    Immutable audit trail; never deleted.
    """

    __tablename__ = "user_tos_acceptances"
    __table_args__ = (
        UniqueConstraint("user_id", "tos_version_id", name="uq_user_tos_acceptance"),
        {"schema": "school"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    # VARCHAR(255) — stores Authentik sub claim; matches users.authentik_id width
    user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    tos_version_id: Mapped[str] = mapped_column(String(36), nullable=False)
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        super().__init__(**kwargs)
