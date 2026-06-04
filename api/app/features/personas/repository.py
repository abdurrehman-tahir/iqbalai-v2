"""Teaching Personas repository — all DB queries for personas."""

from __future__ import annotations

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.personas.models import TeachingPersona

logger = structlog.get_logger(__name__)


class PersonaRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_personas(self) -> list[TeachingPersona]:
        """Return all personas, including inactive ones (admin view)."""
        result = await self._session.execute(select(TeachingPersona))
        return list(result.scalars().all())

    async def get_by_id(self, id: str) -> TeachingPersona | None:
        result = await self._session.execute(
            select(TeachingPersona).where(TeachingPersona.id == id)
        )
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> TeachingPersona | None:
        result = await self._session.execute(
            select(TeachingPersona).where(TeachingPersona.slug == slug)
        )
        return result.scalar_one_or_none()

    async def update(self, persona: TeachingPersona) -> TeachingPersona:
        await self._session.commit()
        await self._session.refresh(persona)
        return persona
