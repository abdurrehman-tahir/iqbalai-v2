"""Unit tests for PersonaService — T-021 acceptance criteria."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import NotFoundError, ValidationError
from app.features.personas.models import TeachingPersona
from app.features.personas.schemas import PersonaUpdate
from app.features.personas.service import PersonaService


@pytest.fixture
def mock_session() -> AsyncMock:
    return AsyncMock()


def _make_persona() -> TeachingPersona:
    """Build a TeachingPersona instance without touching the DB."""
    p = TeachingPersona.__new__(TeachingPersona)
    p.id = "persona-001"
    p.name = "Socratic"
    p.slug = "socratic"
    p.is_custom = False
    p.is_active = True
    p.system_prompt_en = "You are a Socratic tutor. Ask probing questions."
    p.system_prompt_ur = None
    p.system_prompt_sd = None
    p.system_prompt_ps = None
    return p


@pytest.mark.asyncio
async def test_update_persona_prompt_too_long_raises_validation_error(
    mock_session: AsyncMock,
) -> None:
    """system_prompt_en longer than 8000 characters must raise ValidationError."""
    svc = PersonaService(mock_session)
    repo_mock = AsyncMock()
    repo_mock.get_by_id.return_value = _make_persona()
    svc._repo = repo_mock

    oversized_prompt = "x" * 8001
    payload = PersonaUpdate(system_prompt_en=oversized_prompt)

    with pytest.raises(ValidationError):
        await svc.update_persona("persona-001", payload, updated_by="admin-001")


@pytest.mark.asyncio
async def test_update_missing_persona_raises_not_found(mock_session: AsyncMock) -> None:
    """update_persona must raise NotFoundError when the persona does not exist."""
    svc = PersonaService(mock_session)
    repo_mock = AsyncMock()
    repo_mock.get_by_id.return_value = None
    svc._repo = repo_mock

    payload = PersonaUpdate(system_prompt_en="Updated prompt text.")

    with pytest.raises(NotFoundError):
        await svc.update_persona("nonexistent-id", payload, updated_by="admin-001")
