"""Base teaching persona injection — ARCH §8.20 (T-158).

Runtime hook for lecture Q&A / self-study: prepend a **base** persona block to
the system prompt. Adaptive difficulty (#61) is M-14 and must NOT live here.

Student persona *selection* + ``custom_persona_profiles`` learning batch are not
wired yet — until those tables land, this resolves the seeded Friendly Tutor
named persona (``friendly_tutor``) as the static base style.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.personas.repository import PersonaRepository

_DEFAULT_SLUG = "friendly_tutor"
_FALLBACK_PERSONA = (
    "You are a warm, encouraging tutor. You celebrate small wins, use simple "
    "relatable examples, and never make students feel embarrassed for not knowing "
    "something. You guide students gently toward the right answer."
)


def _prompt_for_language(persona: object, language: str) -> str:
    """Pick the multilingual system prompt column, falling back to English."""
    en = str(getattr(persona, "system_prompt_en", "") or "").strip()
    if language == "ur":
        ur = getattr(persona, "system_prompt_ur", None)
        if isinstance(ur, str) and ur.strip():
            return ur.strip()
    if language == "sd":
        sd = getattr(persona, "system_prompt_sd", None)
        if isinstance(sd, str) and sd.strip():
            return sd.strip()
    if language == "ps":
        ps = getattr(persona, "system_prompt_ps", None)
        if isinstance(ps, str) and ps.strip():
            return ps.strip()
    return en or _FALLBACK_PERSONA


async def resolve_base_persona(
    session: AsyncSession,
    *,
    student_user_id: str | None = None,
    language: str = "en",
) -> str:
    """Return the base §8.20 persona text to prepend to a system prompt.

    ``student_user_id`` is accepted for forward-compatibility with per-student
    Custom persona profiles (ARCH §8.20). Today it is unused — selection +
    learned profiles are not yet implemented.
    """
    _ = student_user_id  # reserved for custom_persona_profiles lookup
    repo = PersonaRepository(session)
    persona = await repo.get_by_slug(_DEFAULT_SLUG)
    if persona is None or not persona.is_active:
        return _FALLBACK_PERSONA
    return _prompt_for_language(persona, language)


def prepend_persona(persona_block: str, system_prompt: str) -> str:
    """Concatenate persona STYLE block ahead of the task system prompt."""
    persona = persona_block.strip()
    system = system_prompt.strip()
    if not persona:
        return system
    if not system:
        return persona
    return f"{persona}\n\n{system}"
