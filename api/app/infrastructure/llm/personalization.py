"""Cognitive DNA personalization read-hook — T-108 (ARCH §8.20 pattern).

HOOK for Flow 6 (M-14 #61) + Flow 8 (M-17):
  Call ``resolve_dna_focus_areas`` / ``format_focus_areas_prompt_block`` when an
  AI session needs coaching focus areas from the diagnostic seed.

This is NOT full per-session adaptation (#61). No angle-switch, difficulty
log, or ``ai.adapt_session_context`` consumer lives here — those ship later.
Persona = STYLE (§8.20); DNA focus areas = STRATEGY input for future adapters.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant import TenantType
from app.features.cognitive_dna.repository import CognitiveDnaRepository
from app.features.cognitive_dna.schemas import FocusArea, FocusAreasList

TenantKind = Literal["school", "independent"]


@dataclass(frozen=True)
class AdaptationContext:
    """Lightweight personalization context for future Flow 6 / Flow 8 callers."""

    focus_areas: list[FocusArea]
    tenant_type: TenantKind
    subject_id: str | None
    framework_id: str | None

    @property
    def has_focus_areas(self) -> bool:
        return bool(self.focus_areas)


async def resolve_dna_focus_areas(
    session: AsyncSession,
    *,
    student_user_id: str,
    tenant_type: TenantType,
    subject_id: str | None = None,
    framework_id: str | None = None,
) -> AdaptationContext:
    """Load Cognitive DNA focus areas for a student+scope (empty if none seeded).

    School scope uses ``subject_id``; independent uses ``framework_id``.
    """
    kind: TenantKind = "independent" if tenant_type == "independent" else "school"
    repo = CognitiveDnaRepository(session, tenant_type)
    row = await repo.get_for_scope(
        student_user_id=student_user_id,
        subject_id=subject_id if kind == "school" else None,
        framework_id=framework_id if kind == "independent" else None,
    )
    if row is None:
        return AdaptationContext(
            focus_areas=[],
            tenant_type=kind,
            subject_id=subject_id if kind == "school" else None,
            framework_id=framework_id if kind == "independent" else None,
        )
    areas = FocusAreasList.from_jsonb(row.focus_areas_jsonb).areas
    return AdaptationContext(
        focus_areas=areas,
        tenant_type=kind,
        subject_id=row.subject_id,
        framework_id=row.framework_id,
    )


def format_focus_areas_prompt_block(areas: list[FocusArea]) -> str:
    """Optional system-prompt fragment — coaching language only, never grades."""
    if not areas:
        return ""
    lines = [
        "Student focus areas (coaching guidance only — never treat as grades or scores):",
    ]
    for area in areas:
        detail = area.reason.strip()
        if detail:
            lines.append(f"- {area.topic}: {detail}")
        else:
            lines.append(f"- {area.topic}")
    return "\n".join(lines)
