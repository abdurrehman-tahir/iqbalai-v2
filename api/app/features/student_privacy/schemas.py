"""Pydantic schemas for student #72 teacher-activity privacy (T-162)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

TeacherActivityShareLiteral = Literal["share", "private"]


class TeacherActivityShareRead(BaseModel):
    """Current #72 preference for the school student."""

    teacher_activity_share: TeacherActivityShareLiteral


class TeacherActivityShareUpdate(BaseModel):
    """Toggle #72 share-with-teacher preference."""

    teacher_activity_share: TeacherActivityShareLiteral
