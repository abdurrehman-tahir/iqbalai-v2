"""Self-study session ORM + event tagging — T-210 (Flow 8 §3.11).

Reuses Flow 6 interaction pipeline; sessions are the self-study counterpart to
``lecture_sessions``. Independent sessions never feed Flow 7 (teacher review).
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base, _uuid7
from app.features.self_study.models import SelfStudyTenantType, _tenant_type_enum


class SelfStudySessionStatus(StrEnum):
    ACTIVE = "active"
    ENDED = "ended"


def _session_status_enum(schema: str) -> SAEnum:
    return SAEnum(
        SelfStudySessionStatus,
        name="self_study_sessions_status_enum",
        schema=schema,
        values_callable=lambda items: [item.value for item in items],
        native_enum=True,
        create_type=False,
    )


class SchoolSelfStudySession(AuditMixin, Base):
    """Active / ended self-study session (school)."""

    __tablename__ = "self_study_sessions"
    __table_args__ = (
        Index("ix_self_study_sessions_student_user_id", "student_user_id"),
        {"schema": "school"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    tenant_type: Mapped[SelfStudyTenantType] = mapped_column(
        _tenant_type_enum("school"),
        nullable=False,
        default=SelfStudyTenantType.SCHOOL,
    )
    student_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("school.users.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Locked interaction mode tag for NATS payloads (Flow 8 §3.11).
    mode: Mapped[str] = mapped_column(String(32), nullable=False, default="self_study")
    status: Mapped[SelfStudySessionStatus] = mapped_column(
        _session_status_enum("school"),
        nullable=False,
        default=SelfStudySessionStatus.ACTIVE,
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Optional material / plan context for resume (T-209 state keys).
    material_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    study_plan_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        if "tenant_type" not in kwargs:
            kwargs["tenant_type"] = SelfStudyTenantType.SCHOOL
        if "mode" not in kwargs:
            kwargs["mode"] = "self_study"
        if "status" not in kwargs:
            kwargs["status"] = SelfStudySessionStatus.ACTIVE
        super().__init__(**kwargs)


class IndependentSelfStudySession(AuditMixin, Base):
    """Active / ended self-study session (independent)."""

    __tablename__ = "self_study_sessions"
    __table_args__ = (
        Index("ix_ind_self_study_sessions_student_user_id", "student_user_id"),
        {"schema": "independent"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    tenant_type: Mapped[SelfStudyTenantType] = mapped_column(
        _tenant_type_enum("independent"),
        nullable=False,
        default=SelfStudyTenantType.INDEPENDENT,
    )
    student_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("independent.users.id", ondelete="CASCADE"),
        nullable=False,
    )
    mode: Mapped[str] = mapped_column(String(32), nullable=False, default="self_study")
    status: Mapped[SelfStudySessionStatus] = mapped_column(
        _session_status_enum("independent"),
        nullable=False,
        default=SelfStudySessionStatus.ACTIVE,
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    material_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    study_plan_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        if "tenant_type" not in kwargs:
            kwargs["tenant_type"] = SelfStudyTenantType.INDEPENDENT
        if "mode" not in kwargs:
            kwargs["mode"] = "self_study"
        if "status" not in kwargs:
            kwargs["status"] = SelfStudySessionStatus.ACTIVE
        super().__init__(**kwargs)


SelfStudySession = SchoolSelfStudySession


def event_reaches_flow7(
    *,
    tenant_type: str,
    mode: str,
    teacher_activity_share: str = "share",
) -> bool:
    """Flow 7 consumes school self-study events only when #72=share.

    Independent events never reach a teacher surface (Flow 8 §3.11).
    """
    if tenant_type != "school":
        return False
    if mode != "self_study":
        # Lecture-mode events use the existing lecture pipeline; not this gate.
        return False
    return teacher_activity_share == "share"
