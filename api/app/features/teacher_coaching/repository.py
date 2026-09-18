"""Teacher-coaching repository — T-138 (Flow 5 §3.10 #36).

One row per (teacher, category, weakness_type), per the model's own
docstring — ``get_by_weakness`` is the single-row read/write path T-138's
adaptive logic relies on.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.teacher_coaching.models import (
    IndependentTeacherAiMemory,
    SchoolTeacherAiMemory,
    TeacherResponseType,
)


class SchoolTeacherAiMemoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, memory_id: str) -> SchoolTeacherAiMemory | None:
        return await self._session.get(SchoolTeacherAiMemory, memory_id)

    async def get_by_weakness(
        self, *, teacher_user_id: str, category: str, weakness_type: str
    ) -> SchoolTeacherAiMemory | None:
        result = await self._session.execute(
            select(SchoolTeacherAiMemory).where(
                SchoolTeacherAiMemory.teacher_user_id == teacher_user_id,
                SchoolTeacherAiMemory.category == category,
                SchoolTeacherAiMemory.weakness_type == weakness_type,
            )
        )
        return result.scalar_one_or_none()

    async def list_pending_for_teacher(self, teacher_user_id: str) -> list[SchoolTeacherAiMemory]:
        """Rows with an unactioned suggestion — the teacher-facing "current tips" list."""
        result = await self._session.execute(
            select(SchoolTeacherAiMemory)
            .where(
                SchoolTeacherAiMemory.teacher_user_id == teacher_user_id,
                SchoolTeacherAiMemory.teacher_response == TeacherResponseType.NONE,
            )
            .order_by(SchoolTeacherAiMemory.updated_at.desc())
        )
        return list(result.scalars().all())

    async def list_context_for_teacher(
        self, teacher_user_id: str, *, limit: int
    ) -> list[SchoolTeacherAiMemory]:
        """All memory rows regardless of response status, most-recurring first —
        used as scoring-prompt context (T-134), a broader signal than the
        "pending tips" list above."""
        result = await self._session.execute(
            select(SchoolTeacherAiMemory)
            .where(SchoolTeacherAiMemory.teacher_user_id == teacher_user_id)
            .order_by(SchoolTeacherAiMemory.frequency.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def create(self, memory: SchoolTeacherAiMemory) -> SchoolTeacherAiMemory:
        self._session.add(memory)
        await self._session.commit()
        await self._session.refresh(memory)
        return memory

    async def update(self, memory: SchoolTeacherAiMemory) -> SchoolTeacherAiMemory:
        await self._session.commit()
        await self._session.refresh(memory)
        return memory


class IndependentTeacherAiMemoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, memory_id: str) -> IndependentTeacherAiMemory | None:
        return await self._session.get(IndependentTeacherAiMemory, memory_id)

    async def get_by_weakness(
        self, *, teacher_user_id: str, category: str, weakness_type: str
    ) -> IndependentTeacherAiMemory | None:
        result = await self._session.execute(
            select(IndependentTeacherAiMemory).where(
                IndependentTeacherAiMemory.teacher_user_id == teacher_user_id,
                IndependentTeacherAiMemory.category == category,
                IndependentTeacherAiMemory.weakness_type == weakness_type,
            )
        )
        return result.scalar_one_or_none()

    async def list_pending_for_teacher(
        self, teacher_user_id: str
    ) -> list[IndependentTeacherAiMemory]:
        result = await self._session.execute(
            select(IndependentTeacherAiMemory)
            .where(
                IndependentTeacherAiMemory.teacher_user_id == teacher_user_id,
                IndependentTeacherAiMemory.teacher_response == TeacherResponseType.NONE,
            )
            .order_by(IndependentTeacherAiMemory.updated_at.desc())
        )
        return list(result.scalars().all())

    async def list_context_for_teacher(
        self, teacher_user_id: str, *, limit: int
    ) -> list[IndependentTeacherAiMemory]:
        result = await self._session.execute(
            select(IndependentTeacherAiMemory)
            .where(IndependentTeacherAiMemory.teacher_user_id == teacher_user_id)
            .order_by(IndependentTeacherAiMemory.frequency.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def create(self, memory: IndependentTeacherAiMemory) -> IndependentTeacherAiMemory:
        self._session.add(memory)
        await self._session.commit()
        await self._session.refresh(memory)
        return memory

    async def update(self, memory: IndependentTeacherAiMemory) -> IndependentTeacherAiMemory:
        await self._session.commit()
        await self._session.refresh(memory)
        return memory
