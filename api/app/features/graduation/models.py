"""Graduation ORM models — T-085/T-086."""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base, SoftDeleteMixin, _uuid7


class GraduationRequestStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class GraduationMigrationStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class GraduationRequest(AuditMixin, SoftDeleteMixin, Base):
    """Coordinator-initiated graduation request pending School Admin approval."""

    __tablename__ = "graduation_requests"
    __table_args__ = {"schema": "school"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    student_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("school.users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    school_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("school.schools.id", ondelete="RESTRICT"),
        nullable=False,
    )
    requested_by_user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    approved_by_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[GraduationRequestStatus] = mapped_column(
        SAEnum(
            GraduationRequestStatus,
            name="graduation_request_status",
            schema="school",
            values_callable=lambda items: [item.value for item in items],
            native_enum=True,
            create_type=False,
        ),
        nullable=False,
        default=GraduationRequestStatus.PENDING,
    )
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        super().__init__(**kwargs)


class GraduationMigrationLog(AuditMixin, SoftDeleteMixin, Base):
    """Tracks auto-migration scheduling, attempts, and outcome."""

    __tablename__ = "graduation_migration_log"
    __table_args__ = {"schema": "school"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    student_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("school.users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    graduated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    migration_scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    migration_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    migration_status: Mapped[GraduationMigrationStatus] = mapped_column(
        SAEnum(
            GraduationMigrationStatus,
            name="graduation_migration_status",
            schema="school",
            values_callable=lambda items: [item.value for item in items],
            native_enum=True,
            create_type=False,
        ),
        nullable=False,
        default=GraduationMigrationStatus.PENDING,
        index=True,
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    migrated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        if "migration_attempts" not in kwargs:
            kwargs["migration_attempts"] = 0
        super().__init__(**kwargs)
