"""Model-metadata lint (T-230).

Offline structural audit of the ORM layer against the locked data conventions
(ARCH §4). No DB connection — everything is read from SQLAlchemy metadata, so it
runs in the same offline lane as the OpenAPI/AST gates.

Guards, for every mapped table:
- a primary key exists;
- AuditMixin tables carry created_at/updated_at with a DB-side server_default;
- SoftDeleteMixin tables carry an indexed deleted_at;
- every ForeignKey declares an explicit ondelete AND its column is indexed;
- the stable status/type columns are *native* Postgres enums, not free-text.
"""

from __future__ import annotations

import pytest
from sqlalchemy import Enum as SAEnum
from sqlalchemy import Table

from app.db.base import AuditMixin, Base, SoftDeleteMixin

# Importing the model modules registers their tables on Base.metadata. The alembic
# env only imports Base, so the test is the place that pulls the full model set in.
from app.features.audit import models as audit_models  # noqa: F401
from app.features.exam_syllabi import models as exam_models  # noqa: F401
from app.features.files import models as files_models  # noqa: F401
from app.features.library import models as library_models  # noqa: F401
from app.features.notifications import models as notif_models  # noqa: F401
from app.features.personas import models as persona_models  # noqa: F401
from app.features.subscriptions import models as sub_models  # noqa: F401
from app.features.tos import models as tos_models  # noqa: F401
from app.features.users import models as user_models  # noqa: F401


def _mapped_classes() -> list[type]:
    return [m.class_ for m in Base.registry.mappers]


def _tables() -> list[Table]:
    return list(Base.metadata.tables.values())


def _indexed_column_names(table: Table) -> set[str]:
    """Column names that lead (or appear in) any index on the table."""
    names: set[str] = set()
    for index in table.indexes:
        for col in index.columns:
            names.add(col.name)
    return names


def test_every_table_has_a_primary_key() -> None:
    offenders = [t.name for t in _tables() if len(t.primary_key.columns) == 0]
    assert offenders == [], f"Tables without a primary key: {offenders}"


def test_audit_mixin_tables_have_server_default_timestamps() -> None:
    offenders: list[str] = []
    for cls in _mapped_classes():
        if not issubclass(cls, AuditMixin):
            continue
        table = cls.__table__
        for col_name in ("created_at", "updated_at"):
            col = table.columns[col_name]
            if col.server_default is None:
                offenders.append(f"{table.name}.{col_name}")
    assert offenders == [], f"AuditMixin timestamps missing server_default: {offenders}"


def test_soft_delete_tables_have_indexed_deleted_at() -> None:
    offenders: list[str] = []
    for cls in _mapped_classes():
        if not issubclass(cls, SoftDeleteMixin):
            continue
        table = cls.__table__
        if "deleted_at" not in _indexed_column_names(table):
            offenders.append(table.name)
    assert offenders == [], f"SoftDeleteMixin tables with un-indexed deleted_at: {offenders}"


def test_every_foreign_key_has_ondelete_and_index() -> None:
    no_ondelete: list[str] = []
    not_indexed: list[str] = []
    for table in _tables():
        indexed = _indexed_column_names(table)
        for fk in table.foreign_keys:
            label = f"{table.name}.{fk.parent.name} -> {fk.target_fullname}"
            if fk.ondelete is None:
                no_ondelete.append(label)
            if fk.parent.name not in indexed:
                not_indexed.append(label)
    assert no_ondelete == [], f"Foreign keys missing explicit ondelete: {no_ondelete}"
    assert not_indexed == [], f"Foreign key columns missing an index: {not_indexed}"


# Stable value sets backed by native Postgres enums (ARCH §4.4).
_ENUM_COLUMNS = [
    ("users", "role"),
    ("users", "account_status"),
]

# Varchar-backed enum labels in migrations; ORM uses native_enum=False (create_type=False).
_VARCHAR_ENUM_COLUMNS = [
    ("upload_records", "status"),
    ("platform_reference_books", "content_type"),
    ("platform_reference_books", "status"),
    ("subscription_tiers", "applies_to"),
    ("subscriptions", "subscriber_type"),
    ("subscriptions", "status"),
    ("subscription_payments", "status"),
]


@pytest.mark.parametrize(("table_name", "column_name"), _ENUM_COLUMNS)
def test_stable_columns_are_native_enums(table_name: str, column_name: str) -> None:
    table = Base.metadata.tables[f"school.{table_name}"]
    col = table.columns[column_name]
    assert isinstance(col.type, SAEnum), f"{table_name}.{column_name} is not an Enum type"
    assert col.type.native_enum is True, f"{table_name}.{column_name} is not a native enum"


@pytest.mark.parametrize(("table_name", "column_name"), _VARCHAR_ENUM_COLUMNS)
def test_subscription_enums_use_varchar_storage(table_name: str, column_name: str) -> None:
    table = Base.metadata.tables[f"school.{table_name}"]
    col = table.columns[column_name]
    assert isinstance(col.type, SAEnum), f"{table_name}.{column_name} is not an Enum type"
    assert col.type.native_enum is False, f"{table_name}.{column_name} should use varchar storage"


def _constraint_names(table: Table) -> set[str]:
    return {c.name for c in table.constraints if c.name is not None}


def test_named_check_and_unique_constraints_present() -> None:
    """The hand-authored DB invariants from T-230 must exist by name."""
    topics = Base.metadata.tables["school.syllabus_topics"]
    assert "syllabus_topics_depth_check" in _constraint_names(topics)

    tos = Base.metadata.tables["school.tos_versions"]
    assert "tos_versions_version_number_uq" in _constraint_names(tos)

    disclaimers = Base.metadata.tables["school.disclaimer_versions"]
    assert "disclaimer_versions_version_number_uq" in _constraint_names(disclaimers)


def test_single_custom_persona_partial_unique_index() -> None:
    """Only one custom-slot persona may exist — enforced by a partial unique index."""
    personas = Base.metadata.tables["school.teaching_personas"]
    idx = {i.name: i for i in personas.indexes}
    assert "teaching_personas_custom_slot_uq" in idx
    custom_idx = idx["teaching_personas_custom_slot_uq"]
    assert custom_idx.unique is True
    assert custom_idx.dialect_options["postgresql"]["where"] is not None
