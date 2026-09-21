"""T-158 — base persona prepend helper (ARCH §8.20)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.infrastructure.llm.persona import prepend_persona, resolve_base_persona


def test_prepend_persona_joins_blocks() -> None:
    out = prepend_persona("You are friendly.", "Answer the question.")
    assert out.startswith("You are friendly.")
    assert "Answer the question." in out


@pytest.mark.asyncio
async def test_resolve_base_persona_falls_back_when_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = AsyncMock()

    class _Repo:
        def __init__(self, _session: object) -> None:
            pass

        async def get_by_slug(self, slug: str) -> None:
            return None

    monkeypatch.setattr("app.infrastructure.llm.persona.PersonaRepository", _Repo)
    text = await resolve_base_persona(session, student_user_id="stu-1", language="en")
    assert "encouraging" in text.lower() or "tutor" in text.lower()


@pytest.mark.asyncio
async def test_resolve_base_persona_uses_named_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = AsyncMock()
    persona = MagicMock()
    persona.is_active = True
    persona.system_prompt_en = "Strict tutor voice."
    persona.system_prompt_ur = None
    persona.system_prompt_sd = None
    persona.system_prompt_ps = None

    class _Repo:
        def __init__(self, _session: object) -> None:
            pass

        async def get_by_slug(self, slug: str) -> object:
            assert slug == "friendly_tutor"
            return persona

    monkeypatch.setattr("app.infrastructure.llm.persona.PersonaRepository", _Repo)
    text = await resolve_base_persona(session, language="en")
    assert text == "Strict tutor voice."
