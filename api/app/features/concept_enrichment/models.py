"""Concept enrichment ORM models — T-189 (flow-6 §3.10, #71).

- ``careers``: platform-level controlled vocabulary of Pakistani careers.
  The LLM never writes free-text career links — it may only pick ids from
  this table (T-190).
- ``concept_applications``: PER-CONCEPT cache (shared by every student who
  reaches the concept), keyed by (concept_id, tenant_type). ``concept_id`` is
  the curriculum sub-topic id from the M-14 resolver (session_difficulty
  ``resolve_sub_topic_id``, T-175) — not a hard FK, since sub-topics live in
  curriculum metadata, not one table.
- ``student_simulation_progress``: PER-STUDENT mini-sim state.

School schema (the lecture viewer is school-only until Flow 8); independents
get their own copy later (flow-6 §10).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base, _uuid7


class EnrichmentTenantType(StrEnum):
    SCHOOL = "school"
    INDEPENDENT = "independent"


class ConceptApplicationStatus(StrEnum):
    """Cache row lifecycle. ``pending`` doubles as the generation lock (T-190)."""

    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"


def _tenant_type_enum(schema: str) -> SAEnum:
    # Reuse lectures_tenant_type_enum created by school_0051.
    return SAEnum(
        EnrichmentTenantType,
        name="lectures_tenant_type_enum",
        schema=schema,
        values_callable=lambda items: [item.value for item in items],
        native_enum=True,
        create_type=False,
    )


def _status_enum(schema: str) -> SAEnum:
    return SAEnum(
        ConceptApplicationStatus,
        name="concept_applications_status_enum",
        schema=schema,
        values_callable=lambda items: [item.value for item in items],
        native_enum=True,
        create_type=False,
    )


class Career(AuditMixin, Base):
    """Controlled career vocabulary (platform-level reference data, seeded)."""

    __tablename__ = "careers"
    __table_args__ = (
        UniqueConstraint("slug", name="careers_slug_uq"),
        Index("ix_careers_sector", "sector"),
        {"schema": "school"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    slug: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    sector: Mapped[str] = mapped_column(String(100), nullable=False)
    # list[str] of concept keywords the career relies on (matched against concepts).
    required_concepts: Mapped[list[str]] = mapped_column(JSONB, nullable=False)

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        super().__init__(**kwargs)


class SchoolConceptApplication(AuditMixin, Base):
    """Per-concept enrichment cache (shared across students)."""

    __tablename__ = "concept_applications"
    __table_args__ = (
        UniqueConstraint(
            "concept_id", "tenant_type", name="concept_applications_concept_tenant_uq"
        ),
        Index("ix_concept_applications_status_generated_at", "status", "generated_at"),
        {"schema": "school"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    concept_id: Mapped[str] = mapped_column(String(128), nullable=False)
    # Human-readable concept name used in the prompt + UI header.
    concept_label: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[ConceptApplicationStatus] = mapped_column(
        _status_enum("school"), nullable=False, default=ConceptApplicationStatus.PENDING
    )
    # list[{title, description}] — validated by RealWorldUse on write (T-190).
    real_world_uses: Mapped[list[object]] = mapped_column(JSONB, nullable=False, default=list)
    # list[str] of careers.id — only vocabulary ids, never free text.
    career_link_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    # Structured mini-simulation spec (MiniSimSpec, T-190/T-191); null until ready.
    mini_sim_prompt: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    regen_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tenant_type: Mapped[EnrichmentTenantType] = mapped_column(
        _tenant_type_enum("school"), nullable=False, default=EnrichmentTenantType.SCHOOL
    )

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        if "tenant_type" not in kwargs:
            kwargs["tenant_type"] = EnrichmentTenantType.SCHOOL
        if "status" not in kwargs:
            kwargs["status"] = ConceptApplicationStatus.PENDING
        if "real_world_uses" not in kwargs:
            kwargs["real_world_uses"] = []
        if "career_link_ids" not in kwargs:
            kwargs["career_link_ids"] = []
        super().__init__(**kwargs)


class SchoolStudentSimulationProgress(AuditMixin, Base):
    """One student's saved mini-simulation state for one concept (T-191)."""

    __tablename__ = "student_simulation_progress"
    __table_args__ = (
        UniqueConstraint(
            "student_user_id", "concept_id", name="student_simulation_progress_student_concept_uq"
        ),
        Index("ix_student_simulation_progress_student_user_id", "student_user_id"),
        Index("ix_student_simulation_progress_concept_id", "concept_id"),
        {"schema": "school"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    # CASCADE: per-student data dies with the user (ARCH §4.6 users→student data).
    student_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("school.users.id", ondelete="CASCADE"), nullable=False
    )
    concept_id: Mapped[str] = mapped_column(String(128), nullable=False)
    sim_state: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    tenant_type: Mapped[EnrichmentTenantType] = mapped_column(
        _tenant_type_enum("school"), nullable=False, default=EnrichmentTenantType.SCHOOL
    )

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        if "tenant_type" not in kwargs:
            kwargs["tenant_type"] = EnrichmentTenantType.SCHOOL
        if "sim_state" not in kwargs:
            kwargs["sim_state"] = {}
        super().__init__(**kwargs)
