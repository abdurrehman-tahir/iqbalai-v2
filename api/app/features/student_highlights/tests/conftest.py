"""Fixtures for M-15 student_highlights tests.

- ``pg``: the real-Postgres fixture (skips without DB_URL).
- T-187 side-effect isolation (CLAUDE.md rule 12): ``flashcard.created`` is
  never actually published from unit/DB tests; tests that assert on it use
  the ``published_flashcards`` mock.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.features.student_highlights.tests.pg_support import pg
from app.features.student_questions import answer_pipeline

__all__ = ["pg", "published_flashcards"]


@pytest.fixture(autouse=True)
def published_flashcards(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    mock = AsyncMock()
    monkeypatch.setattr(answer_pipeline, "publish_flashcard_created", mock)
    return mock
