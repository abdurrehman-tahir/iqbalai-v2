"""Subject ORM model — the school-scoped subject catalogue (school schema, T-041).

Per flow-2 §3.2 a Subject is a school-scoped catalogue entry: ``{school_id, name,
language}``. The ``(school_id, name)`` tuple is unique within a school but not
globally. A Subject is independent of any Grade — it only becomes "offered" when a
``GradeSubjectOffering`` row links it to a Grade (T-044, out of scope here).

``status`` (active | archived) is a **domain state**, distinct from the §4.4
soft-delete (``deleted_at``): archiving keeps the row queryable and still occupying
its unique ``(school_id, name)`` slot, whereas a soft-delete frees that slot. Both
mechanisms coexist on this table.

ORM conventions mirror the sibling tenant-root tables (``districts`` / ``schools``):
``String(36)`` ``_uuid7`` PK + ``AuditMixin``/``SoftDeleteMixin`` rather than the
not-yet-landed native-UUID ``IdMixin`` (codebase-wide deferral, AUDIT_LOG.md) — this
keeps ``school_id`` FK-type-compatible with ``school.schools.id``.
"""

from __future__ import annotations

from enum import StrEnum

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base, SoftDeleteMixin, _uuid7


class SubjectStatus(StrEnum):
    """Lifecycle state of a subject catalogue entry (flow-2 §3.2)."""

    ACTIVE = "active"
    ARCHIVED = "archived"


class Subject(AuditMixin, SoftDeleteMixin, Base):
    """A school-scoped subject catalogue entry (ARCH §3.18, flow-2 §3.2).

    Owned by the Coordinator (and inherited by higher roles per §6.19). The
    ``school_id`` FK uses ``ON DELETE RESTRICT`` (§4.6 protect-the-parent default).
    Name uniqueness is scoped to active (non-deleted) rows so a soft-deleted name can
    be re-created — matching the ``districts``/``schools`` partial-unique pattern.
    """

    __tablename__ = "subjects"
    __table_args__ = (
        Index(
            "subjects_school_name_uq",
            "school_id",
            "name",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_subjects_school_id", "school_id"),
        {"schema": "school"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    school_id: Mapped[str] = mapped_column(
        ForeignKey("school.schools.id", ondelete="RESTRICT"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # Short locale/language code (e.g. "en", "ur"). Plain code string, not a FK —
    # matches the districts.language_preference precedent: there is no editable
    # languages reference table at this stage (flow-2 §3.1).
    language: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[SubjectStatus] = mapped_column(
        SAEnum(
            SubjectStatus,
            name="subjects_status_enum",
            schema="school",
            values_callable=lambda e: [m.value for m in e],
            create_type=False,
        ),
        nullable=False,
        default=SubjectStatus.ACTIVE,
        server_default=SubjectStatus.ACTIVE.value,
    )

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        super().__init__(**kwargs)
