"""Student enrollment API schemas — T-077."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.features.student_enrollments.models import StudentEnrollmentStatus
from app.features.users.models import UserAccountStatus


class StudentEnrollmentCreate(BaseModel):
    """Coordinator enrolls a student into a grade (optional section)."""

    display_name: str = Field(min_length=1, max_length=255)
    email: str = Field(min_length=3, max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    section_id: str | None = Field(
        default=None,
        description="Target section; omit to use the grade default-internal section",
    )


class EnrolledStudentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    display_name: str
    status: UserAccountStatus


class StudentEnrollmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    school_id: str
    student_user_id: str
    grade_id: str
    section_id: str
    academic_session: str
    status: StudentEnrollmentStatus
    enrolled_at: datetime
    student: EnrolledStudentRead
