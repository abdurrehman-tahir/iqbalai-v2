"""Shared fixtures for student_questions tests.

T-186: ``_persist_answer`` now looks up the question's highlight to create a
flashcard. Unit tests here run against ``AsyncMock`` sessions, so default the
lookup to "no highlight" — flashcard behaviour is covered in
``app/features/student_highlights/tests``.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.features.student_questions import answer_pipeline


@pytest.fixture(autouse=True)
def _no_highlight_for_answers(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = MagicMock()
    repo.get_by_question_id = AsyncMock(return_value=None)
    monkeypatch.setattr(answer_pipeline, "StudentHighlightRepository", MagicMock(return_value=repo))
