"""Next-day review ORM models — T-195 (Flow 7 §3.1 / §3.6 / §3.8).

School-schema only (mini-lectures / reviews excluded from independent tenant).
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base, _uuid7


class LectureReviewStatus(StrEnum):
    """Lifecycle of a teacher review card (ARCH §4.9 — stable native enum)."""

    PENDING = "pending"
    COMPLETED = "completed"
    DISMISSED = "dismissed"


def _lecture_review_status_enum() -> SAEnum:
    return SAEnum(
        LectureReviewStatus,
        name="lecture_reviews_status_enum",
        schema="school",
        values_callable=lambda items: [item.value for item in items],
        native_enum=True,
        create_type=False,
    )


class LectureReview(AuditMixin, Base):
    """One overnight review card for a lecture / GSO / calendar day.

    Tenant-tagged by living in the ``school`` schema only (§3.16 — independent
    excluded). ``acted_actions`` is JSONB list so multiple teacher actions are
    allowed per review (Flow 7 §3.6).
    """

    __tablename__ = "lecture_reviews"
    __table_args__ = (
        UniqueConstraint(
            "lecture_id",
            "gso_id",
            "review_date",
            name="lecture_reviews_lecture_gso_date_uq",
        ),
        Index("ix_lecture_reviews_lecture_id", "lecture_id"),
        Index("ix_lecture_reviews_gso_id", "gso_id"),
        Index("ix_lecture_reviews_mini_lecture_id", "mini_lecture_id"),
        Index("ix_lecture_reviews_review_date", "review_date"),
        Index("ix_lecture_reviews_status", "status"),
        {"schema": "school"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    # Parent lecture (Flow 7 §3.8). CASCADE: review has no meaning without lecture.
    lecture_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("school.lectures.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Review unit is the Grade-Subject offering (Flow 7 / Flow 2).
    gso_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("school.grade_subject_offerings.id", ondelete="RESTRICT"),
        nullable=False,
    )
    review_date: Mapped[date] = mapped_column(Date, nullable=False)
    ai_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    reflective_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[LectureReviewStatus] = mapped_column(
        _lecture_review_status_enum(),
        nullable=False,
        default=LectureReviewStatus.PENDING,
        server_default=LectureReviewStatus.PENDING.value,
    )
    pending_action: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    dismissed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    # Multiple teacher actions allowed per review (Flow 7 §3.6).
    acted_actions: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    # Optional mini-lecture published from this review; SET NULL if mini deleted.
    mini_lecture_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("school.lectures.id", ondelete="SET NULL"),
        nullable=True,
    )

    def __init__(self, **kwargs: Any) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        if "acted_actions" not in kwargs:
            kwargs["acted_actions"] = []
        if "status" not in kwargs:
            kwargs["status"] = LectureReviewStatus.PENDING
        if "pending_action" not in kwargs:
            kwargs["pending_action"] = True
        if "ai_summary" not in kwargs:
            kwargs["ai_summary"] = ""
        if "reflective_prompt" not in kwargs:
            kwargs["reflective_prompt"] = ""
        super().__init__(**kwargs)


class ReviewReply(AuditMixin, Base):
    """Teacher reply to a student inside a review cluster."""

    __tablename__ = "review_replies"
    __table_args__ = (
        Index("ix_review_replies_review_id", "review_id"),
        Index("ix_review_replies_student_user_id", "student_user_id"),
        {"schema": "school"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    review_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("school.lecture_reviews.id", ondelete="CASCADE"),
        nullable=False,
    )
    cluster_id: Mapped[str] = mapped_column(String(100), nullable=False)
    student_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("school.users.id", ondelete="CASCADE"),
        nullable=False,
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)

    def __init__(self, **kwargs: Any) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        super().__init__(**kwargs)


class SkippedCluster(AuditMixin, Base):
    """Cluster the teacher excluded from mini-lecture regeneration."""

    __tablename__ = "skipped_clusters"
    __table_args__ = (
        UniqueConstraint(
            "review_id",
            "cluster_ref",
            name="skipped_clusters_review_cluster_uq",
        ),
        Index("ix_skipped_clusters_review_id", "review_id"),
        {"schema": "school"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    review_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("school.lecture_reviews.id", ondelete="CASCADE"),
        nullable=False,
    )
    cluster_ref: Mapped[str] = mapped_column(String(200), nullable=False)
    skipped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    def __init__(self, **kwargs: Any) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        super().__init__(**kwargs)


class ReviewClassificationFailure(AuditMixin, Base):
    """DLQ for cluster-level classification / pipeline failures (T-197)."""

    __tablename__ = "review_classification_failures"
    __table_args__ = (
        Index("ix_review_classification_failures_school_id", "school_id"),
        Index("ix_review_classification_failures_gso_id", "gso_id"),
        {"schema": "school"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    school_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("school.schools.id", ondelete="CASCADE"),
        nullable=False,
    )
    gso_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("school.grade_subject_offerings.id", ondelete="CASCADE"),
        nullable=False,
    )
    cluster_ref: Mapped[str] = mapped_column(String(200), nullable=False)
    error: Mapped[str] = mapped_column(Text, nullable=False)
    failed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    def __init__(self, **kwargs: Any) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        super().__init__(**kwargs)
