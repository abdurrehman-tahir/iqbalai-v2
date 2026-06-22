"""Bulk import ORM model — T-037."""

from __future__ import annotations

import enum

from datetime import datetime

from sqlalchemy import DateTime, Enum as SAEnum, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base, _uuid7


class BulkImportStatus(str, enum.Enum):
    """Coordinator bulk import lifecycle — dry-run then commit (T-037 / T-079)."""

    DRY_RUN_COMPLETE = "dry_run_complete"
    COMMITTED = "committed"
    COMMITTED_WITH_ERRORS = "committed_with_errors"


class BulkImport(AuditMixin, Base):
    """Tracks a coordinator bulk student import job (validation only in M-02)."""

    __tablename__ = "bulk_imports"
    __table_args__ = {"schema": "school"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    school_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    imported_by_user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    upload_id: Mapped[str] = mapped_column(String(36), nullable=False)
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_report_jsonb: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    status: Mapped[BulkImportStatus] = mapped_column(
        SAEnum(
            BulkImportStatus,
            name="bulkimportstatus",
            schema="school",
            values_callable=lambda statuses: [s.value for s in statuses],
            native_enum=True,
            create_type=False,
        ),
        nullable=False,
        default=BulkImportStatus.DRY_RUN_COMPLETE,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        super().__init__(**kwargs)
