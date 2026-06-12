"""Notification ORM model — lives in the school schema (T-023)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base, SoftDeleteMixin, _uuid7


class Notification(AuditMixin, SoftDeleteMixin, Base):
    """One notification row per recipient per event.

    Soft-deleted rows are swept by Celery beat after 90 days (Phase 2, per T-023).
    """

    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_recipient", "recipient_user_id"),
        Index("ix_notifications_namespace", "feature_namespace"),
        Index("ix_notifications_is_read", "is_read"),
        Index("ix_notifications_school_id", "school_id"),
        {"schema": "school"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    # VARCHAR(255) — stores Authentik sub claim; matches users.authentik_id width
    recipient_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    # One of the 7 locked namespaces — validated at publish time in infrastructure layer
    feature_namespace: Mapped[str] = mapped_column(String(50), nullable=False)
    # e.g. "account.invite_sent", "quiz.grade_released"
    template_key: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    # Extra payload serialised as JSON string — callers parse as needed
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Tenant scoping — NULL for platform-level notifications
    school_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        super().__init__(**kwargs)
