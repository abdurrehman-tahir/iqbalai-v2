"""School-tier Content Library ORM models — T-054 (flow-3 §3.3–§3.4)."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base, SoftDeleteMixin, _uuid7


class LibraryContentType(StrEnum):
    CURRICULUM = "curriculum"
    REFERENCE = "reference"


class LibraryVisibility(StrEnum):
    PRIVATE = "private"
    SCHOOL_PUBLIC = "school_public"


class LibraryIngestionStatus(StrEnum):
    PENDING = "pending"
    INGESTING = "ingesting"
    AVAILABLE = "available"
    FAILED = "failed"


def _pg_enum(enum_cls: type[StrEnum], name: str) -> SAEnum:
    return SAEnum(
        enum_cls,
        name=name,
        schema="school",
        values_callable=lambda e: [m.value for m in e],
        native_enum=False,
        create_type=False,
    )


class SchoolLibraryItem(AuditMixin, SoftDeleteMixin, Base):
    """A curriculum or reference book in a school's content library."""

    __tablename__ = "library_items"
    __table_args__ = (
        Index("ix_library_items_school_id", "school_id"),
        Index("ix_library_items_created_by", "created_by"),
        Index("ix_library_items_sha256", "sha256"),
        Index("ix_library_items_subject_id", "subject_id"),
        Index(
            "library_items_school_sha256_uq",
            "school_id",
            "sha256",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        {"schema": "school"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    school_id: Mapped[str] = mapped_column(
        ForeignKey("school.schools.id", ondelete="RESTRICT"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[LibraryContentType] = mapped_column(
        _pg_enum(LibraryContentType, "library_items_content_type_enum"),
        nullable=False,
    )
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="en")
    subject_id: Mapped[str | None] = mapped_column(
        ForeignKey("school.subjects.id", ondelete="SET NULL"),
        nullable=True,
    )
    grade_level_ordinal: Mapped[int | None] = mapped_column(Integer, nullable=True)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    ingestion_status: Mapped[LibraryIngestionStatus] = mapped_column(
        _pg_enum(LibraryIngestionStatus, "library_items_ingestion_status_enum"),
        nullable=False,
        default=LibraryIngestionStatus.PENDING,
    )
    topic_tree_jsonb: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    created_by: Mapped[str] = mapped_column(
        ForeignKey("school.users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    visibility: Mapped[LibraryVisibility] = mapped_column(
        _pg_enum(LibraryVisibility, "library_items_visibility_enum"),
        nullable=False,
        default=LibraryVisibility.PRIVATE,
    )
    ingestion_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class SchoolLibraryItemSelection(AuditMixin, SoftDeleteMixin, Base):
    """Tracks which user is using a library item (dedup + privacy per uploader)."""

    __tablename__ = "library_item_selections"
    __table_args__ = (
        Index("ix_library_item_selections_library_item_id", "library_item_id"),
        Index("ix_library_item_selections_user_id", "user_id"),
        Index(
            "library_item_selections_item_user_uq",
            "library_item_id",
            "user_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        {"schema": "school"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    library_item_id: Mapped[str] = mapped_column(
        ForeignKey("school.library_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("school.users.id", ondelete="CASCADE"),
        nullable=False,
    )
    selected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now() AT TIME ZONE 'UTC'"),
    )


class SchoolLibraryItemChunk(AuditMixin, Base):
    """Chunk metadata for an ingested school library item (vectors live in Qdrant)."""

    __tablename__ = "library_item_chunks"
    __table_args__ = (
        Index("ix_library_item_chunks_library_item_id", "library_item_id"),
        Index("ix_library_item_chunks_school_id", "school_id"),
        Index(
            "library_item_chunks_item_index_uq",
            "library_item_id",
            "chunk_index",
            unique=True,
        ),
        {"schema": "school"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    library_item_id: Mapped[str] = mapped_column(
        ForeignKey("school.library_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    school_id: Mapped[str] = mapped_column(
        ForeignKey("school.schools.id", ondelete="RESTRICT"),
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    qdrant_point_id: Mapped[str] = mapped_column(String(36), nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
