"""Platform Library ORM model — T-024."""

from __future__ import annotations

from enum import StrEnum

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base, SoftDeleteMixin, _uuid7


class ReferenceBookContentType(StrEnum):
    """Whether a book is a curriculum text or a supplementary reference."""

    CURRICULUM = "curriculum"
    REFERENCE = "reference"


class ReferenceBookStatus(StrEnum):
    """Ingestion lifecycle of a platform reference book."""

    PROCESSING = "processing"
    AVAILABLE = "available"
    INGESTION_FAILED = "ingestion_failed"


def _pg_enum(enum_cls: type[StrEnum], name: str) -> SAEnum:
    """Native Postgres enum bound to the school schema (ARCH §4.4)."""
    return SAEnum(
        enum_cls,
        name=name,
        schema="school",
        values_callable=lambda e: [m.value for m in e],
        native_enum=True,
        create_type=False,
    )


class PlatformReferenceBook(AuditMixin, SoftDeleteMixin, Base):
    """Metadata record for a Platform Admin-uploaded reference book.

    One row per uploaded PDF.  The actual file bytes live in MinIO;
    text chunks live in the Qdrant ``platform_chunks`` collection.
    """

    __tablename__ = "platform_reference_books"
    __table_args__ = {"schema": "school"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    # FK to upload_records.id — the raw file pipeline record. RESTRICT: keep the
    # upload row as long as a library book references it.
    upload_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("school.upload_records.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[ReferenceBookContentType] = mapped_column(
        _pg_enum(ReferenceBookContentType, "platform_reference_books_content_type_enum"),
        nullable=False,
        default=ReferenceBookContentType.REFERENCE,
    )
    # Optional free-text subject tag for RAG payload filtering
    subject_tag: Mapped[str | None] = mapped_column(String(255), nullable=True)
    grade_range_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    grade_range_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="en")
    # Global SHA-256 dedup key
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[ReferenceBookStatus] = mapped_column(
        _pg_enum(ReferenceBookStatus, "platform_reference_books_status_enum"),
        nullable=False,
        default=ReferenceBookStatus.PROCESSING,
    )
    qdrant_collection: Mapped[str] = mapped_column(
        String(100), nullable=False, default="platform_chunks"
    )
    # Set after ingestion completes
    chunk_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
