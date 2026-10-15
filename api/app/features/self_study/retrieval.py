"""Self-study RAG retrieval config — T-210 (Flow 8 §3.11 / ARCH §7).

Flow names this "Pattern P (personal pool)". ARCH §7.1 maps self-study Q&A to
**Pattern A** (agentic) whose primary tool searches ``student_upload_chunks``.
Overlays:
  - school → §7.21 cross-grade curriculum (grades ≤ student grade)
  - independent → exam-syllabus collection if selected, else LLM knowledge only
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

PrimaryCollection = Literal["student_upload_chunks"]
OverlayKind = Literal["cross_grade_curriculum", "exam_syllabus", "ai_knowledge"]


@dataclass(frozen=True, slots=True)
class SelfStudyRetrievalPlan:
    """Declarative retrieval plan for a self-study Q&A turn."""

    pattern: Literal["A"]  # Agentic RAG wraps personal-pool Pattern S tools
    primary_collection: PrimaryCollection
    mode: Literal["self_study"]
    tenant_type: Literal["school", "independent"]
    overlays: tuple[OverlayKind, ...]
    allow_web_fallback: bool = False


def build_self_study_retrieval_plan(
    *,
    tenant_type: Literal["school", "independent"],
    has_exam_syllabus: bool = False,
) -> SelfStudyRetrievalPlan:
    """Return the locked retrieval plan for this tenant (no retrieval I/O)."""
    if tenant_type == "school":
        overlays: tuple[OverlayKind, ...] = ("cross_grade_curriculum",)
    elif has_exam_syllabus:
        overlays = ("exam_syllabus",)
    else:
        overlays = ("ai_knowledge",)
    return SelfStudyRetrievalPlan(
        pattern="A",
        primary_collection="student_upload_chunks",
        mode="self_study",
        tenant_type=tenant_type,
        overlays=overlays,
        allow_web_fallback=False,
    )
