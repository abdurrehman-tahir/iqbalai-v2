"""Section ORM model — optional sections under a grade (school schema, T-044)."""

from __future__ import annotations

from enum import StrEnum

from sqlalchemy import Boolean, Enum as SAEnum, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base, SoftDeleteMixin, _uuid7

DEFAULT_INTERNAL_NAME = "__default__"


class SectionStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class Section(AuditMixin, SoftDeleteMixin, Base):
    """An optional section within a grade (ARCH §3.18, flow-2 §3.3)."""

    __tablename__ = "sections"
    __table_args__ = (
        Index(
            "sections_grade_name_uq",
            "grade_id",
            "name",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_sections_grade_id", "grade_id"),
        {"schema": "school"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    grade_id: Mapped[str] = mapped_column(
        ForeignKey("school.grades.id", ondelete="RESTRICT"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_default_internal: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    status: Mapped[SectionStatus] = mapped_column(
        SAEnum(
            SectionStatus,
            name="sections_status_enum",
            schema="school",
            values_callable=lambda e: [m.value for m in e],
            create_type=False,
        ),
        nullable=False,
        default=SectionStatus.ACTIVE,
        server_default=SectionStatus.ACTIVE.value,
    )

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        super().__init__(**kwargs)
