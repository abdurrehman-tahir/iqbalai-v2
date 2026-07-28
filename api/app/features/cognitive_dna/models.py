"""Provisional Cognitive DNA seed ORM — T-102 (Flow 4 §3.6 / Flow 9 #83 hook).

MINIMAL seed only: per-topic confidence + focus areas written by the diagnostic
(T-106). Flow 9 / M-18 will extend this with mistake history, pass probability,
spaced-repetition state, etc. — do not add those columns here.

TODO(Flow-9/M-18): extend CognitiveDna with mistake tracking, predictions,
spaced-repetition scheduling, and Question Bank linkage when M-18 is unblocked.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base, SoftDeleteMixin, _uuid7


class CognitiveDnaSource(StrEnum):
    """How this DNA row was last seeded. Additive-only — Flow 9 may ADD VALUE."""

    DIAGNOSTIC = "diagnostic"


class CognitiveDnaTenantType(StrEnum):
    """Redundant with schema isolation but required by the T-102 seed shape."""

    SCHOOL = "school"
    INDEPENDENT = "independent"


def _source_enum(schema: str) -> SAEnum:
    return SAEnum(
        CognitiveDnaSource,
        name="cognitive_dna_source_enum",
        schema=schema,
        values_callable=lambda items: [item.value for item in items],
        native_enum=True,
        create_type=False,
    )


def _tenant_type_enum(schema: str) -> SAEnum:
    return SAEnum(
        CognitiveDnaTenantType,
        name="cognitive_dna_tenant_type_enum",
        schema=schema,
        values_callable=lambda items: [item.value for item in items],
        native_enum=True,
        create_type=False,
    )


class SchoolCognitiveDna(AuditMixin, SoftDeleteMixin, Base):
    """School-schema Cognitive DNA seed (provisional — Flow 9 / M-18 extensible)."""

    __tablename__ = "cognitive_dna"
    __table_args__ = {"schema": "school"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    tenant_type: Mapped[CognitiveDnaTenantType] = mapped_column(
        _tenant_type_enum("school"),
        nullable=False,
        default=CognitiveDnaTenantType.SCHOOL,
    )
    student_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("school.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Nullable opaque IDs — school may later tighten FKs; avoid forcing subjects here.
    subject_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    framework_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    topic_confidence_jsonb: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    focus_areas_jsonb: Mapped[list[object]] = mapped_column(JSONB, nullable=False)
    source: Mapped[CognitiveDnaSource] = mapped_column(
        _source_enum("school"),
        nullable=False,
        default=CognitiveDnaSource.DIAGNOSTIC,
    )
    last_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        if "tenant_type" not in kwargs:
            kwargs["tenant_type"] = CognitiveDnaTenantType.SCHOOL
        if "source" not in kwargs:
            kwargs["source"] = CognitiveDnaSource.DIAGNOSTIC
        if "topic_confidence_jsonb" not in kwargs:
            kwargs["topic_confidence_jsonb"] = {}
        if "focus_areas_jsonb" not in kwargs:
            kwargs["focus_areas_jsonb"] = []
        super().__init__(**kwargs)


class IndependentCognitiveDna(AuditMixin, SoftDeleteMixin, Base):
    """Independent-schema Cognitive DNA seed (provisional — Flow 9 / M-18 extensible)."""

    __tablename__ = "cognitive_dna"
    __table_args__ = {"schema": "independent"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    tenant_type: Mapped[CognitiveDnaTenantType] = mapped_column(
        _tenant_type_enum("independent"),
        nullable=False,
        default=CognitiveDnaTenantType.INDEPENDENT,
    )
    student_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("independent.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # No cross-schema FK to school.exam_frameworks (§4.21) — opaque UUID only.
    subject_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    framework_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    topic_confidence_jsonb: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    focus_areas_jsonb: Mapped[list[object]] = mapped_column(JSONB, nullable=False)
    source: Mapped[CognitiveDnaSource] = mapped_column(
        _source_enum("independent"),
        nullable=False,
        default=CognitiveDnaSource.DIAGNOSTIC,
    )
    last_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        if "tenant_type" not in kwargs:
            kwargs["tenant_type"] = CognitiveDnaTenantType.INDEPENDENT
        if "source" not in kwargs:
            kwargs["source"] = CognitiveDnaSource.DIAGNOSTIC
        if "topic_confidence_jsonb" not in kwargs:
            kwargs["topic_confidence_jsonb"] = {}
        if "focus_areas_jsonb" not in kwargs:
            kwargs["focus_areas_jsonb"] = []
        super().__init__(**kwargs)
