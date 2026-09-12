"""7-dimension lecture-version quality scoring — T-134 (Flow 5 §3.6 #32, ARCH §7.10).

A *separate* LLM call from generation, using an objective evaluator persona
and the smaller ``SCORING_MODEL`` (task id ``"scoring"`` in
``infrastructure/llm/client.py``) — never folded into the generation prompt.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.infrastructure.llm.types import PromptCall

PROMPT_VERSION = "lecture_scoring.v1"


class LectureScoringInput(BaseModel):
    topic: str = Field(min_length=1, max_length=500)
    original_body: str = Field(min_length=1, max_length=6000)
    edited_body: str = Field(min_length=1, max_length=6000)
    diff: str = Field(max_length=4000)
    edit_summary: list[str] = Field(default_factory=list)
    active_ms: int = Field(ge=0)
    edits_count: int = Field(ge=0)
    char_delta: int = Field(ge=0)
    teacher_region: str | None = None
    innovation_record_context: list[str] = Field(default_factory=list)
    is_first_version: bool


class LectureScoringOutput(BaseModel):
    """Raw LLM output — the caller clamps ranges and enforces the two locked
    overrides (``voice_quality`` null for text-only edits, ``ai_learning`` = 0
    on the first version) itself rather than trusting the model to comply.
    """

    originality: int
    depth: int
    cultural_relevance: int
    engagement: int
    alignment: int
    voice_quality: int | None = None
    ai_learning: int


SYSTEM = """You are an objective instructional-quality evaluator reviewing a \
teacher's edit of an AI-generated lecture draft. You are NOT the author — \
score critically and fairly, the way a curriculum reviewer would.

Score the EDITED version across exactly 7 dimensions, each an integer:

- originality (0-10): how distinctively the teacher reshaped the AI draft \
(rewording alone scores low; substantive restructuring, new examples, or \
original framing score high).
- depth (0-10): conceptual depth beyond a surface-level explanation.
- cultural_relevance (0-5): use of locally relevant examples for the \
teacher's region, if a region is given; if no region is given, judge general \
cultural relevance and do not penalize for the missing region.
- engagement (0-5): how likely the content is to capture student attention.
- alignment (0-10): how well the content stays aligned with the stated topic.
- voice_quality (0-5 or null): quality of the voice-dictated portion of the \
edit, if any; if the edit summary shows no voice edit, return null.
- ai_learning (0-10): how much the teacher's edit reflects acting on their \
prior coaching feedback (given below as "innovation record context"); if no \
context is given, or this is the lecture's first version, return 0.

Return ONLY valid JSON, no markdown fences, no commentary:
{{
  "originality": <int>,
  "depth": <int>,
  "cultural_relevance": <int>,
  "engagement": <int>,
  "alignment": <int>,
  "voice_quality": <int or null>,
  "ai_learning": <int>
}}"""


def _format_context_list(label: str, items: list[str]) -> str:
    if not items:
        return f"{label}: none"
    bullets = "\n".join(f"- {item}" for item in items)
    return f"{label}:\n{bullets}"


def render(input_data: LectureScoringInput) -> PromptCall:
    """Pure render — unit-testable, no I/O."""
    edit_annotations = _format_context_list(
        "Auto-detected edit annotations", input_data.edit_summary
    )
    innovation_context = _format_context_list(
        "Innovation record context (prior coaching)", input_data.innovation_record_context
    )
    user = (
        f"Topic: {input_data.topic}\n"
        f"Teacher region: {input_data.teacher_region or 'unknown'}\n"
        f"First version: {input_data.is_first_version}\n\n"
        f"--- Original AI-generated draft ---\n{input_data.original_body}\n\n"
        f"--- Teacher-edited version ---\n{input_data.edited_body}\n\n"
        f"--- Diff (original -> edited) ---\n{input_data.diff}\n\n"
        f"{edit_annotations}\n\n"
        "Edit-session effort data for this version:\n"
        f"- active editing time (ms): {input_data.active_ms}\n"
        f"- edit operations: {input_data.edits_count}\n"
        f"- characters changed: {input_data.char_delta}\n\n"
        f"{innovation_context}"
        "\n\nScore the edited version as JSON per the rules above."
    )
    return PromptCall(
        version=PROMPT_VERSION,
        system=SYSTEM,
        user=user,
        temperature=0.2,
        max_tokens=400,
    )
