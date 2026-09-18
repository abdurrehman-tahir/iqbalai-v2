"""Teacher delivery tips / technique demo / real-world examples — T-124.

Flow 5 §3.15 (#28, #41) / ARCH §8.6. Second, separate LLM call fired after
lecture generation completes. Deliberately grounded in general teaching
knowledge only — NOT the curriculum/reference RAG chunks used by
``lecture_generate_v1`` (the opposite grounding direction, by design).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.infrastructure.llm.types import PromptCall

PROMPT_VERSION = "lecture_teacher_tips.v1"


class LectureTeacherTipsInput(BaseModel):
    topic: str = Field(min_length=1, max_length=500)
    subject_name: str = Field(min_length=1, max_length=200)
    grade_level_ordinal: int = Field(ge=1, le=20)
    target_language: Literal["en", "ur", "sd", "ps"] = "en"


class RealWorldExampleOut(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=2000)


class LectureTeacherTipsOutput(BaseModel):
    delivery_tips: list[str] = Field(min_length=3, max_length=5)
    technique_demo: str = Field(min_length=1, max_length=2000)
    real_world_examples: list[RealWorldExampleOut] = Field(min_length=2, max_length=2)


SYSTEM = """You are a veteran teacher-training coach helping a secondary-school \
teacher deliver a lecture effectively.

Return ONLY valid JSON:
{{
  "delivery_tips": ["Tip 1", "Tip 2", "Tip 3"],
  "technique_demo": "A short demonstration of one specific teaching technique for this topic.",
  "real_world_examples": [
    {{"title": "Example title", "text": "Example body"}},
    {{"title": "Example title", "text": "Example body"}}
  ]
}}

CRITICAL RULES:
- Use ONLY your general teaching knowledge. Do NOT reference or assume any specific
  curriculum or reference book content — these aids are generated fresh for this
  topic, not grounded in uploaded documents.
- Delivery tips: 3-5 concise, actionable tips specific to teaching {topic} at
  Grade {grade_level_ordinal} in {subject_name}.
- Technique demo: one specific, concrete teaching technique (e.g. a Socratic question
  sequence, a quick demonstration, an analogy) the teacher could use live in class.
- Real-world examples: exactly 2 examples connecting {topic} to everyday life, chosen
  to be culturally relevant and recognizable to students in Pakistan.
- Respond in {language}.
- No markdown fences or commentary — JSON only.
"""


def render(input_data: LectureTeacherTipsInput) -> PromptCall:
    """Pure render — unit-testable, no I/O."""
    system = SYSTEM.format(
        topic=input_data.topic,
        grade_level_ordinal=input_data.grade_level_ordinal,
        subject_name=input_data.subject_name,
        language=input_data.target_language,
    )
    user = (
        f"Topic: {input_data.topic}\n"
        f"Subject: {input_data.subject_name}\n"
        f"Grade: {input_data.grade_level_ordinal}\n\n"
        "Generate the delivery tips, technique demo, and real-world examples as JSON."
    )
    return PromptCall(
        version=PROMPT_VERSION,
        system=system,
        user=user,
        temperature=0.6,
        max_tokens=1200,
    )
