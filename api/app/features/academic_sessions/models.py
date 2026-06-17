"""Academic Session ORM model — school-scoped session lookup (school schema, T-042).

Per flow-2 §3.3 Grades pin to an ``academic_session`` label (e.g. "2025-2026").
Sessions are stored in a lightweight lookup table per school; exactly one row may be
``is_active=true`` at a time. The school's ``active_academic_session`` column mirrors
the active row's label for fast reads.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base, SoftDeleteMixin, _uuid7


class AcademicSession(AuditMixin, SoftDeleteMixin, Base):
    """A school-scoped academic session label (ARCH §3.18, flow-2 §3.3)."""

    __tablename__ = "academic_sessions"
    __table_args__ = (
        Index(
            "academic_sessions_school_label_uq",
            "school_id",
            "label",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_academic_sessions_school_id", "school_id"),
        {"schema": "school"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    school_id: Mapped[str] = mapped_column(
        ForeignKey("school.schools.id", ondelete="RESTRICT"),
        nullable=False,
    )
    label: Mapped[str] = mapped_column(String(50), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        super().__init__(**kwargs)
