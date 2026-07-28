"""Diagnostic attempt ORM — T-103 (Flow 4 §3.6 lifecycle).

Table ``diagnostics`` in both schemas. Status enum is not_taken | in_progress |
completed (retake = new row after 30-day cooldown, not a fourth status).
Question generation (T-104), UI (T-105), DNA seeding (T-106) are out of scope.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base, SoftDeleteMixin, _uuid7


class DiagnosticStatus(StrEnum):
    NOT_TAKEN = "not_taken"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class DiagnosticTenantType(StrEnum):
    SCHOOL = "school"
    INDEPENDENT = "independent"


def _status_enum(schema: str) -> SAEnum:
    return SAEnum(
        DiagnosticStatus,
        name="diagnostics_status_enum",
        schema=schema,
        values_callable=lambda items: [item.value for item in items],
        native_enum=True,
        create_type=False,
    )


def _tenant_type_enum(schema: str) -> SAEnum:
    return SAEnum(
        DiagnosticTenantType,
        name="diagnostics_tenant_type_enum",
        schema=schema,
        values_callable=lambda items: [item.value for item in items],
        native_enum=True,
        create_type=False,
    )


class SchoolDiagnostic(AuditMixin, SoftDeleteMixin, Base):
    """School-schema diagnostic attempt — scoped per subject."""

    __tablename__ = "diagnostics"
    __table_args__ = {"schema": "school"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    tenant_type: Mapped[DiagnosticTenantType] = mapped_column(
        _tenant_type_enum("school"),
        nullable=False,
        default=DiagnosticTenantType.SCHOOL,
    )
    student_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("school.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subject_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    framework_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    status: Mapped[DiagnosticStatus] = mapped_column(
        _status_enum("school"),
        nullable=False,
        default=DiagnosticStatus.NOT_TAKEN,
    )
    questions_jsonb: Mapped[list[object]] = mapped_column(JSONB, nullable=False)
    answers_jsonb: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        if "tenant_type" not in kwargs:
            kwargs["tenant_type"] = DiagnosticTenantType.SCHOOL
        if "status" not in kwargs:
            kwargs["status"] = DiagnosticStatus.NOT_TAKEN
        if "questions_jsonb" not in kwargs:
            kwargs["questions_jsonb"] = []
        if "answers_jsonb" not in kwargs:
            kwargs["answers_jsonb"] = {}
        super().__init__(**kwargs)


class IndependentDiagnostic(AuditMixin, SoftDeleteMixin, Base):
    """Independent-schema diagnostic attempt — scoped per exam framework."""

    __tablename__ = "diagnostics"
    __table_args__ = {"schema": "independent"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    tenant_type: Mapped[DiagnosticTenantType] = mapped_column(
        _tenant_type_enum("independent"),
        nullable=False,
        default=DiagnosticTenantType.INDEPENDENT,
    )
    student_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("independent.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # No cross-schema FK to school.exam_frameworks (§4.21) — opaque UUID.
    subject_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    framework_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    status: Mapped[DiagnosticStatus] = mapped_column(
        _status_enum("independent"),
        nullable=False,
        default=DiagnosticStatus.NOT_TAKEN,
    )
    questions_jsonb: Mapped[list[object]] = mapped_column(JSONB, nullable=False)
    answers_jsonb: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        if "tenant_type" not in kwargs:
            kwargs["tenant_type"] = DiagnosticTenantType.INDEPENDENT
        if "status" not in kwargs:
            kwargs["status"] = DiagnosticStatus.NOT_TAKEN
        if "questions_jsonb" not in kwargs:
            kwargs["questions_jsonb"] = []
        if "answers_jsonb" not in kwargs:
            kwargs["answers_jsonb"] = {}
        super().__init__(**kwargs)
