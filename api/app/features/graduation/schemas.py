"""Graduation API schemas — T-085/T-086."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.features.graduation.models import GraduationRequestStatus


class GraduationRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    student_user_id: str
    school_id: str
    requested_by_user_id: str
    approved_by_user_id: str | None = None
    status: GraduationRequestStatus
    requested_at: datetime
    approved_at: datetime | None = None


class GraduationRequestCreate(BaseModel):
    student_user_id: str


class StudentGraduationStatusRead(BaseModel):
    is_graduated: bool = False
    school_read_only: bool = False
    lecture_read_only: bool = False
    self_study_enabled: bool = True
    migrated_out: bool = False
    graduated_at: datetime | None = None
    migration_scheduled_at: datetime | None = None
    graduation_message: str | None = None
    pending_graduation_request: GraduationRequestRead | None = None
