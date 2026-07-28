"""Question Bank hook for diagnostic questions — T-104.

BLOCKED-HOOK: Question Bank #74 (Flow 9 / M-18). When banked questions exist for
the subject/framework, prefer them; until then this always returns None and the
caller falls back to LLM generation.
"""

from __future__ import annotations

from typing import Any

from app.features.diagnostics.schemas import DiagnosticQuestion


async def try_question_bank(
    *,
    tenant_kind: str,
    subject_id: str | None = None,
    framework_id: str | None = None,
    grade_label: str = "",
    limit: int = 20,
) -> list[DiagnosticQuestion] | None:
    """Return banked questions when available; None means LLM fallback.

    Parameters are accepted so the future bank lookup has a stable API.
    """
    void: dict[str, Any] = {
        "tenant_kind": tenant_kind,
        "subject_id": subject_id,
        "framework_id": framework_id,
        "grade_label": grade_label,
        "limit": limit,
    }
    _ = void  # reserved for M-18 bank query
    return None
