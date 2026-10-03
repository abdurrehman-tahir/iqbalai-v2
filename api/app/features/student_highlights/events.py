"""``flashcard.created`` publisher — T-187 (flow-6 §3.6, #58 → Flow 8 SRS).

M-15 is publish-only: the consumer that schedules cards (py-fsrs, question
queue #76) is Flow 9 / M-18; Flow 8 / M-17 surfaces the deck.

Wire subject: the ticket's ``flashcard.created`` is published as
``student.flashcard.created`` — ARCH §9.3 locks ``<domain>.<entity>.<event>``
with a fixed domain list, and only ``student.>`` (stream ``student-events``,
§9.4) would capture it; a bare ``flashcard.*`` subject is stored by no stream.
The §9.3 append for this subject is raised for approval in the M-15 PR.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.features.lectures.events import publish_student_lecture_event
from app.features.student_highlights.models import SchoolStudentFlashcard

FLASHCARD_CREATED = "student.flashcard.created"


class FlashcardCreatedV1(BaseModel):
    """Payload for ``student.flashcard.created`` (schema_version 1, ARCH §9.5).

    Carries references only (card + student + concept + lecture) plus tenant
    context — never the card's front/back text, which stays in the DB.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    flashcard_id: str
    student_user_id: str
    lecture_id: str | None
    concept_tag: str | None
    source_highlight_id: str | None
    source_type: Literal["highlight", "manual"]
    school_id: str
    tenant_type: Literal["school", "independent"]
    created_at: datetime


def flashcard_created_payload(
    card: SchoolStudentFlashcard, *, school_id: str | None
) -> FlashcardCreatedV1:
    return FlashcardCreatedV1(
        flashcard_id=card.id,
        student_user_id=card.student_user_id,
        lecture_id=card.lecture_id,
        concept_tag=card.concept_tag,
        source_highlight_id=card.source_highlight_id,
        source_type=card.source_type.value,
        school_id=school_id or "",
        tenant_type=card.tenant_type.value,
        created_at=card.created_at,
    )


async def publish_flashcard_created(card: SchoolStudentFlashcard, *, school_id: str | None) -> None:
    """Publish AFTER the DB commit (§9.9). Best-effort: never raises."""
    payload = flashcard_created_payload(card, school_id=school_id)
    await publish_student_lecture_event(
        event_type=FLASHCARD_CREATED,
        payload=payload.model_dump(mode="json"),
    )
