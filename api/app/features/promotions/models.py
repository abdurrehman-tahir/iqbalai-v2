"""Grade promotion request ORM — T-250 (Flow 2 §3.4 / ARCH §6.21)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base, SoftDeleteMixin, _uuid7


class GradePromotionRequestStatus(StrEnum):
    """§6.21 state machine values (stable → native Postgres enum)."""

    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTING = "executing"
    EXECUTED = "executed"
    EXPIRED = "expired"
    FAILED = "failed"


class GradePromotionRequest(AuditMixin, SoftDeleteMixin, Base):
    """Coordinator-initiated per-grade promotion pending School Admin approval.

    School-schema only. Uses AuditMixin + SoftDeleteMixin + explicit ``school_id``
    (same pattern as ``GraduationRequest`` / ``Grade`` — not TenantMixin).
    """

    __tablename__ = "grade_promotion_requests"
    __table_args__ = (
        # At most one active pending request per initiating grade (re-initiate after
        # reject/expire/executed is allowed — those statuses are terminal).
        Index(
            "grade_promotion_requests_pending_grade_uq",
            "initiating_grade_id",
            unique=True,
            postgresql_where=text("status = 'pending_approval' AND deleted_at IS NULL"),
        ),
        Index("ix_grade_promotion_requests_school_id", "school_id"),
        Index("ix_grade_promotion_requests_initiating_grade_id", "initiating_grade_id"),
        Index("ix_grade_promotion_requests_target_grade_id", "target_grade_id"),
        Index("ix_grade_promotion_requests_status", "status"),
        {"schema": "school"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    school_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("school.schools.id", ondelete="RESTRICT"),
        nullable=False,
    )
    initiating_grade_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("school.grades.id", ondelete="RESTRICT"),
        nullable=False,
    )
    # Populated during execute_promotion (T-253); null while pending/approved.
    target_grade_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("school.grades.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Intent at request time (Flow 2 §3.4: target Grade name + session).
    target_academic_session: Mapped[str] = mapped_column(String(50), nullable=False)
    target_grade_name: Mapped[str] = mapped_column(String(200), nullable=False)
    initiated_by_coordinator_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("school.users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    # Spec sketch: exclusion_list_jsonb — UUID array of held-back student_user_ids.
    exclusion_list_jsonb: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    status: Mapped[GradePromotionRequestStatus] = mapped_column(
        SAEnum(
            GradePromotionRequestStatus,
            name="grade_promotion_request_status",
            schema="school",
            values_callable=lambda items: [item.value for item in items],
            native_enum=True,
            create_type=False,
        ),
        nullable=False,
        default=GradePromotionRequestStatus.PENDING_APPROVAL,
        server_default=GradePromotionRequestStatus.PENDING_APPROVAL.value,
    )
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    approved_by_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("school.users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    executed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    def __init__(self, **kwargs: Any) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        if "exclusion_list_jsonb" not in kwargs:
            kwargs["exclusion_list_jsonb"] = []
        if "retry_count" not in kwargs:
            kwargs["retry_count"] = 0
        if "status" not in kwargs:
            kwargs["status"] = GradePromotionRequestStatus.PENDING_APPROVAL
        super().__init__(**kwargs)
