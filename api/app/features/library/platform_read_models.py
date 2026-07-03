"""Read-only ORM mapping for cross-schema platform library view (T-073)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PlatformReferenceBookReadonly(Base):
    """Maps to independent.platform_reference_books view → school.platform_reference_books."""

    __tablename__ = "platform_reference_books"
    __table_args__ = {"schema": "independent", "info": {"is_view": True}}

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    upload_id: Mapped[str] = mapped_column(String(36), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str] = mapped_column(String(20), nullable=False)
    subject_tag: Mapped[str | None] = mapped_column(String(255), nullable=True)
    grade_range_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    grade_range_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    language: Mapped[str] = mapped_column(String(10), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    qdrant_collection: Mapped[str] = mapped_column(String(100), nullable=False)
    chunk_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
