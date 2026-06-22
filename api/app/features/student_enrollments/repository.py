"""Student enrollment repository — DB access (T-077)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import not_deleted
from app.features.student_enrollments.models import StudentEnrollment, StudentEnrollmentStatus


class StudentEnrollmentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, enrollment_id: str) -> StudentEnrollment | None:
        result = await self._session.execute(
            select(StudentEnrollment).where(
                StudentEnrollment.id == enrollment_id,
                not_deleted(StudentEnrollment),
            )
        )
        return result.scalar_one_or_none()

    async def get_active_by_student_session(
        self, student_user_id: str, academic_session: str
    ) -> StudentEnrollment | None:
        result = await self._session.execute(
            select(StudentEnrollment).where(
                StudentEnrollment.student_user_id == student_user_id,
                StudentEnrollment.academic_session == academic_session,
                StudentEnrollment.status == StudentEnrollmentStatus.ACTIVE,
                not_deleted(StudentEnrollment),
            )
        )
        return result.scalar_one_or_none()

    async def create(self, enrollment: StudentEnrollment) -> StudentEnrollment:
        self._session.add(enrollment)
        await self._session.commit()
        await self._session.refresh(enrollment)
        return enrollment
