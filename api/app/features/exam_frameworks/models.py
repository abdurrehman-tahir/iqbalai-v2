"""Exam Framework ORM models — school schema, platform-shared (T-091).

Three platform-tier tables (Flow 4 §3.5, ARCH §3.19). They live in the ``school``
schema and are exposed read-only to the ``independent`` schema via cross-schema
views (ARCH §3.16 / §4.21) — never duplicated, never cross-schema FKs.

- ``exam_frameworks``          — thin Platform-Admin-owned metadata record.
- ``framework_study_plans``    — append-only versioned AI-generated plan (§4.18).
- ``student_framework_selections`` — student <-> framework link (both tenant types;
  multiple active selections allowed per student, so NO unique-per-student index).
"""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base, SoftDeleteMixin, _uuid7


class FrameworkStatus(str, enum.Enum):
    """Exam-framework definition lifecycle (Flow 4 §3.5.1).

    draft -> researching -> pending_approval -> published -> refreshing ->
    (published new version) ; published/any -> deprecated (existing students
    grandfathered). Additive-only per ARCH §4.9.
    """

    DRAFT = "draft"
    RESEARCHING = "researching"
    PENDING_APPROVAL = "pending_approval"
    PUBLISHED = "published"
    REFRESHING = "refreshing"
    DEPRECATED = "deprecated"


class StudyPlanStatus(str, enum.Enum):
    """Per-version study-plan lifecycle. Independent view exposes ``approved`` only."""

    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    SUPERSEDED = "superseded"


class SelectionStatus(str, enum.Enum):
    """Student framework-selection lifecycle (Flow 4 §3.5.3)."""

    ACTIVE = "active"
    ABANDONED = "abandoned"


class SelectionTenantType(str, enum.Enum):
    """Which tenant schema the selecting student belongs to (school-schema table
    holds selections from both tenant types; student_user_id is cross-schema so
    it is a plain column, not a FK)."""

    SCHOOL = "school"
    INDEPENDENT = "independent"


class ExamFramework(AuditMixin, SoftDeleteMixin, Base):
    """Platform-Admin-owned exam framework definition (thin metadata record)."""

    __tablename__ = "exam_frameworks"
    __table_args__ = ({"schema": "school"},)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Exam this framework targets, e.g. "Matric Punjab Board — Physics".
    exam_target: Mapped[str] = mapped_column(String(255), nullable=False)
    # Region scoping for student filtering (T-096), e.g. "Punjab", "Sindh", "any".
    region: Mapped[str] = mapped_column(String(100), nullable=False)
    # Postgres int[] — the grade band this framework serves, e.g. {9,10}.
    target_grade_range: Mapped[list[int]] = mapped_column(ARRAY(Integer), nullable=False)
    # BCP-47 language tag, e.g. "en", "ur".
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="en")
    status: Mapped[FrameworkStatus] = mapped_column(
        SAEnum(
            FrameworkStatus,
            name="exam_framework_status",
            schema="school",
            values_callable=lambda statuses: [s.value for s in statuses],
            native_enum=True,
            create_type=False,
        ),
        nullable=False,
        default=FrameworkStatus.DRAFT,
    )
    # Platform Admin user id. Plain column (actor id may be cross-schema/Authentik),
    # mirrors graduation_requests.requested_by_user_id — no FK by design.
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        if "status" not in kwargs:
            kwargs["status"] = FrameworkStatus.DRAFT
        super().__init__(**kwargs)


class FrameworkStudyPlan(AuditMixin, Base):
    """Immutable, append-only versioned AI-generated study plan (§4.18 versioning).

    One row per version of a framework's plan. Never updated in place except for
    the approval columns + status transition; new content -> new version row.
    """

    __tablename__ = "framework_study_plans"
    __table_args__ = (
        UniqueConstraint(
            "framework_id", "version", name="framework_study_plans_framework_version_uq"
        ),
        {"schema": "school"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    framework_id: Mapped[str] = mapped_column(
        String(36),
        # Versions have no meaning without their framework -> CASCADE (§4.6, skill Rule 3).
        ForeignKey("school.exam_frameworks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    # §3.5.2 structure: topics[], weekly_pacing[], exam_strategy. Validated on write
    # by schemas.FrameworkStudyPlanContent (§4.10).
    content_jsonb: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    # Cited source list: [{"url": ..., "title": ...}, ...] — schemas.SourceCitation.
    sources_cited_jsonb: Mapped[list[object]] = mapped_column(JSONB, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Nullable: approval may not have happened yet (§4.7).
    approved_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[StudyPlanStatus] = mapped_column(
        SAEnum(
            StudyPlanStatus,
            name="framework_study_plan_status",
            schema="school",
            values_callable=lambda statuses: [s.value for s in statuses],
            native_enum=True,
            create_type=False,
        ),
        nullable=False,
        default=StudyPlanStatus.DRAFT,
    )

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        if "status" not in kwargs:
            kwargs["status"] = StudyPlanStatus.DRAFT
        super().__init__(**kwargs)


class StudentFrameworkSelection(AuditMixin, SoftDeleteMixin, Base):
    """A student's selection of an exam framework, pinned to a plan version.

    Multiple *active* selections per student are allowed (Flow 4 §3.5.3) — there is
    deliberately NO unique constraint on student_user_id.
    """

    __tablename__ = "student_framework_selections"
    __table_args__ = ({"schema": "school"},)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    tenant_type: Mapped[SelectionTenantType] = mapped_column(
        SAEnum(
            SelectionTenantType,
            name="student_framework_selection_tenant_type",
            schema="school",
            values_callable=lambda types: [t.value for t in types],
            native_enum=True,
            create_type=False,
        ),
        nullable=False,
    )
    # Cross-schema (school OR independent users) -> plain indexed column, no FK (§4.21).
    student_user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    framework_id: Mapped[str] = mapped_column(
        String(36),
        # Protect: a selection must not orphan; frameworks are soft-deleted/deprecated.
        ForeignKey("school.exam_frameworks.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    pinned_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[SelectionStatus] = mapped_column(
        SAEnum(
            SelectionStatus,
            name="student_framework_selection_status",
            schema="school",
            values_callable=lambda statuses: [s.value for s in statuses],
            native_enum=True,
            create_type=False,
        ),
        nullable=False,
        default=SelectionStatus.ACTIVE,
    )
    selected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        if "status" not in kwargs:
            kwargs["status"] = SelectionStatus.ACTIVE
        super().__init__(**kwargs)
