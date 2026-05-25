"""Pydantic v2 schemas for the audit log feature (T-025)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditLogEntryRead(BaseModel):
    """Read schema for a single audit log row.

    metadata_json is returned as a raw string — callers parse JSON as needed.
    Intentionally no write schema: audit rows are created only via the
    infrastructure helper (app/infrastructure/audit/log.py), never via the API.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    action: str
    actor_id: str | None
    actor_role: str | None
    target_type: str | None
    target_id: str | None
    school_id: str | None
    district_id: str | None
    metadata_json: str | None
    ip_address: str | None
    created_at: datetime
