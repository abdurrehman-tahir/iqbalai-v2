"""District and School ORM models — the tenant-root tables (school schema).

Per ARCH §3.3 these tables are **NOT** tenant-scoped: they *are* the tenants.
Access is admin-only and controlled by role, so they carry **no RLS policy** —
unlike the tenant-scoped tables (``users``, ``lectures``, …) which use
``school_id``/``district_id`` + a ``<table>_isolation`` policy. District-Admin
scoping (a District Admin only sees their district's schools) is enforced at the
repository/role layer in T-029, not at the DB RLS layer.

Org hierarchy (ARCH §3.1): District -> School -> (School Admin, Coordinator,
Teacher, Student). Scope IDs cascade downward from creation.
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base, SoftDeleteMixin, _uuid7


class District(AuditMixin, SoftDeleteMixin, Base):
    """A district — top of the org hierarchy (ARCH §3.1, §3.3).

    Not tenant-scoped (no RLS). Soft-deletable so deactivation is one-way and
    reversible only via restore, per the launch deactivation rule (flow-2 §3.1).
    """

    __tablename__ = "districts"
    __table_args__ = (
        Index(
            "districts_name_uq",
            "name",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        {"schema": "school"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # Optional descriptive metadata captured at creation (flow-2 §3.1). `region` is a
    # free-text geographic label; `language_preference` is a short locale/language code
    # (e.g. "en", "ur"). Both are genuinely optional → nullable per §4.7. Kept as a plain
    # code string (not a FK) — there is no editable language reference table at this stage.
    region: Mapped[str | None] = mapped_column(String(200), nullable=True)
    language_preference: Mapped[str | None] = mapped_column(String(20), nullable=True)

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        super().__init__(**kwargs)


class School(AuditMixin, SoftDeleteMixin, Base):
    """A school within a district (ARCH §3.1, §3.3).

    Not tenant-scoped (no RLS); access controlled by role. ``district_id`` FK uses
    ``ON DELETE RESTRICT`` — a district with schools cannot be hard-deleted out from
    under them (§4.6 protect-the-parent default). School name is unique within its
    district, not globally.
    """

    __tablename__ = "schools"
    __table_args__ = (
        Index(
            "schools_district_name_uq",
            "district_id",
            "name",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_schools_district_id", "district_id"),
        {"schema": "school"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    district_id: Mapped[str] = mapped_column(
        ForeignKey("school.districts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # Denormalized mirror of the active academic_sessions.label (T-042).
    active_academic_session: Mapped[str | None] = mapped_column(String(50), nullable=True)

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        super().__init__(**kwargs)
