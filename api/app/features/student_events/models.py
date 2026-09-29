"""student_events analytics store — Flow 6 §3.8 / T-174.

M-00 backlog claimed this table; it was never shipped. Created here as the
Analytics Consumer destination (school + independent schemas). Partitioning
is deferred; monthly/7-year retention is a future ops concern.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, _uuid7


class StudentEventTenantType(StrEnum):
    SCHOOL = "school"
    INDEPENDENT = "independent"


def _tenant_type_enum(schema: str) -> SAEnum:
    return SAEnum(
        StudentEventTenantType,
        name="student_events_tenant_type_enum",
        schema=schema,
        values_callable=lambda items: [item.value for item in items],
        native_enum=True,
        create_type=False,
    )


class SchoolStudentEvent(Base):
    """Long-term analytics event store (school schema)."""

    __tablename__ = "student_events"
    __table_args__ = (
        Index("ix_student_events_tenant_id", "tenant_id"),
        Index("ix_student_events_user_id", "user_id"),
        Index("ix_student_events_session_id", "session_id"),
        Index("ix_student_events_event_type", "event_type"),
        Index("ix_student_events_occurred_at", "occurred_at"),
        {"schema": "school"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    tenant_type: Mapped[StudentEventTenantType] = mapped_column(
        _tenant_type_enum("school"),
        nullable=False,
        default=StudentEventTenantType.SCHOOL,
    )
    tenant_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    session_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    lecture_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    event_payload_jsonb: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        if "event_payload_jsonb" not in kwargs:
            kwargs["event_payload_jsonb"] = {}
        super().__init__(**kwargs)


class IndependentStudentEvent(Base):
    """Long-term analytics event store (independent schema)."""

    __tablename__ = "student_events"
    __table_args__ = (
        Index("ix_ind_student_events_tenant_id", "tenant_id"),
        Index("ix_ind_student_events_user_id", "user_id"),
        Index("ix_ind_student_events_session_id", "session_id"),
        Index("ix_ind_student_events_event_type", "event_type"),
        Index("ix_ind_student_events_occurred_at", "occurred_at"),
        {"schema": "independent"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    tenant_type: Mapped[StudentEventTenantType] = mapped_column(
        _tenant_type_enum("independent"),
        nullable=False,
        default=StudentEventTenantType.INDEPENDENT,
    )
    tenant_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    session_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    lecture_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    event_payload_jsonb: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        if "event_payload_jsonb" not in kwargs:
            kwargs["event_payload_jsonb"] = {}
        super().__init__(**kwargs)


# Compatibility alias used by docs / consumers.
StudentEvent = SchoolStudentEvent
