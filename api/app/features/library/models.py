"""Platform Library ORM model — T-024."""

from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base, SoftDeleteMixin, _uuid7


class PlatformReferenceBook(AuditMixin, SoftDeleteMixin, Base):
    """Metadata record for a Platform Admin-uploaded reference book.

    One row per uploaded PDF.  The actual file bytes live in MinIO;
    text chunks live in the Qdrant ``platform_chunks`` collection.
    """

    __tablename__ = "platform_reference_books"
    __table_args__ = {"schema": "school"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    # FK to upload_records.id — the raw file pipeline record
    upload_id: Mapped[str] = mapped_column(String(36), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    # curriculum | reference
    content_type: Mapped[str] = mapped_column(String(20), nullable=False, default="reference")
    # Optional free-text subject tag for RAG payload filtering
    subject_tag: Mapped[str | None] = mapped_column(String(255), nullable=True)
    grade_range_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    grade_range_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="en")
    # Global SHA-256 dedup key
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # processing | available | ingestion_failed
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="processing")
    qdrant_collection: Mapped[str] = mapped_column(
        String(100), nullable=False, default="platform_chunks"
    )
    # Set after ingestion completes
    chunk_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
