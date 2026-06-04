"""Pydantic schemas for Exam Syllabi endpoints — T-020."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SyllabusTopicRead(BaseModel):
    """Response schema for a single SyllabusTopic."""

    id: str
    syllabus_id: str
    parent_id: str | None
    title: str
    depth: int
    order_index: int
    created_at: datetime

    model_config = {"from_attributes": True}


class SyllabusTopicCreate(BaseModel):
    """Payload for creating a new SyllabusTopic."""

    syllabus_id: str
    parent_id: str | None = None
    title: str = Field(..., max_length=255)
    order_index: int = Field(default=0)


class ExamSyllabusRead(BaseModel):
    """Response schema for a single ExamSyllabus."""

    id: str
    name: str
    exam_board: str
    region: str | None
    grade_range_min: int | None
    grade_range_max: int | None
    language: str
    version_number: int
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ExamSyllabusCreate(BaseModel):
    """Payload for creating a new ExamSyllabus."""

    name: str = Field(..., max_length=255)
    exam_board: str = Field(..., max_length=100)
    region: str | None = None
    grade_range_min: int | None = None
    grade_range_max: int | None = None
    language: str = Field(default="en")


class ExamSyllabusUpdate(BaseModel):
    """Payload for updating an ExamSyllabus (all fields optional)."""

    name: str | None = None
    exam_board: str | None = None
    region: str | None = None
    grade_range_min: int | None = None
    grade_range_max: int | None = None
    language: str | None = None
