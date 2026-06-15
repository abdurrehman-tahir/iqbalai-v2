"""Bulk import Pydantic schemas — T-037."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class BulkImportRowResult(BaseModel):
    """Per-row dry-run validation outcome."""

    row_number: int
    status: Literal["valid", "invalid"]
    errors: list[str] = Field(default_factory=list)
    data: dict[str, str] | None = None


class BulkImportRead(BaseModel):
    """Bulk import job returned to the client."""

    id: str
    school_id: str
    imported_by_user_id: str
    upload_id: str
    total_rows: int
    success_rows: int
    failed_rows: int
    status: str
    rows: list[BulkImportRowResult]
    created_at: datetime
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}
