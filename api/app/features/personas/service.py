"""Teaching Personas service — business logic for persona management."""

from __future__ import annotations

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.features.personas.models import TeachingPersona
from app.features.personas.repository import PersonaRepository
from app.features.personas.schemas import PersonaUpdate

logger = structlog.get_logger(__name__)

# Maximum characters for any system prompt field — enforced in service layer
_MAX_PROMPT_CHARS = 8000


class PersonaService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = PersonaRepository(session)

    async def list_personas(self) -> list[TeachingPersona]:
        """List all personas (including inactive) for admin overview."""
        return await self._repo.list_personas()

    async def get_persona(self, id: str) -> TeachingPersona:
        """Fetch a persona by ID; raises NotFoundError if missing."""
        persona = await self._repo.get_by_id(id)
        if persona is None:
            raise NotFoundError(f"Teaching persona '{id}' not found")
        return persona

    async def update_persona(
        self,
        id: str,
        payload: PersonaUpdate,
        updated_by: str,
    ) -> TeachingPersona:
        """Update persona fields supplied in the payload.

        Only non-None fields are written. Changes apply to NEW sessions only;
        existing cached sessions continue using the old system prompt until they
        expire or are explicitly flushed.

        Validates:
        - system_prompt_en, if provided, must be ≤ 8000 characters.
        """
        persona = await self.get_persona(id)

        if payload.system_prompt_en is not None:
            if len(payload.system_prompt_en) > _MAX_PROMPT_CHARS:
                raise ValidationError(
                    f"system_prompt_en must be ≤ {_MAX_PROMPT_CHARS} characters "
                    f"(got {len(payload.system_prompt_en)})"
                )
            persona.system_prompt_en = payload.system_prompt_en

        if payload.system_prompt_ur is not None:
            persona.system_prompt_ur = payload.system_prompt_ur

        if payload.system_prompt_sd is not None:
            persona.system_prompt_sd = payload.system_prompt_sd

        if payload.system_prompt_ps is not None:
            persona.system_prompt_ps = payload.system_prompt_ps

        if payload.is_active is not None:
            persona.is_active = payload.is_active

        updated = await self._repo.update(persona)
        logger.info(
            "teaching_persona_updated",
            persona_id=updated.id,
            slug=updated.slug,
            by=updated_by,
        )
        return updated
