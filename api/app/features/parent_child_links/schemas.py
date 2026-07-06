"""Pydantic schemas for parent-child links — T-081."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.features.parent_child_links.models import ParentChildLinkStatus


class ParentLinkRequestCreate(BaseModel):
    student_email: str = Field(min_length=3, max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ParentChildLinkRead(BaseModel):
    id: str
    parent_user_id: str
    student_user_id: str
    status: ParentChildLinkStatus
    parent_name: str | None = None
    student_name: str | None = None
    student_email: str | None = None
    approved_at: datetime | None = None
    revoked_at: datetime | None = None
    read_only_access: bool = False
    created_at: datetime


class ParentConnectionsRead(BaseModel):
    parent_state: str
    links: list[ParentChildLinkRead]


class StudentLinkRequestList(BaseModel):
    pending: list[ParentChildLinkRead]


class StudentConnectionsRead(BaseModel):
    access_state: str
    linked_parents: list[ParentChildLinkRead]
    link_history: list[ParentChildLinkRead]


class ParentStudentAccessStateRead(BaseModel):
    student_user_id: str
    access_state: str
    read_only_access: bool
