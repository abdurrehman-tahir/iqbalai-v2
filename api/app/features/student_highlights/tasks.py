"""Student highlights / flashcards Celery tasks (T-193).

Thin wrapper (business logic in flashcard_notifications.py); disposable-engine
``run_db`` per CLAUDE.md rule 11. Platform sweep over all students, so
``@shared_task`` like the other nightly sweeps.
"""

from __future__ import annotations

from celery import shared_task

from app.db.celery_async import run_db
from app.features.student_highlights.flashcard_notifications import send_flashcard_batch


@shared_task(name="flashcards.batch_notification", queue="notifications")  # type: ignore[misc]
def batch_notification() -> int:
    """Nightly (23:15 PKT) in-app batch: "N new flashcards from today" (flow-6 §7)."""
    return run_db(send_flashcard_batch)
