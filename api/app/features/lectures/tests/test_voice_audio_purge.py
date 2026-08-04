"""Voice-audio retention purge task tests — T-121 (#25, flow-5 §6 Limits)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.features.lectures.tasks import _purge_expired_voice_audio_async, purge_expired_voice_audio


def test_purge_task_delegates_to_run_db() -> None:
    with patch(
        "app.features.lectures.tasks.run_db", return_value={"purged_count": 3}
    ) as mock_run_db:
        result = purge_expired_voice_audio()

    assert result == {"purged_count": 3}
    mock_run_db.assert_called_once()


def _fake_turn(turn_id: str, audio_storage_key: str | None = "voice-sessions/vs-1/0.webm") -> Any:
    turn = MagicMock()
    turn.id = turn_id
    turn.audio_storage_key = audio_storage_key
    return turn


@pytest.mark.asyncio
async def test_purge_async_deletes_blob_and_marks_purged(monkeypatch: pytest.MonkeyPatch) -> None:
    expired_turns = [_fake_turn("turn-1"), _fake_turn("turn-2", "voice-sessions/vs-1/1.webm")]
    fake_repo = MagicMock(
        list_with_unpurged_audio_older_than=AsyncMock(return_value=expired_turns),
        mark_audio_purged=AsyncMock(),
    )
    # `_purge_expired_voice_audio_async` does a deferred `from X import Y` — patch
    # the source modules so the fresh import picks up the fakes.
    monkeypatch.setattr(
        "app.features.lectures.repository.LectureVoiceTurnRepository", lambda _session: fake_repo
    )
    mock_delete = MagicMock()
    monkeypatch.setattr("app.infrastructure.storage.client.delete_object", mock_delete)

    session = AsyncMock()
    result = await _purge_expired_voice_audio_async(session)

    assert result == {"purged_count": 2}
    assert mock_delete.call_count == 2
    mock_delete.assert_any_call("audio", "voice-sessions/vs-1/0.webm")
    mock_delete.assert_any_call("audio", "voice-sessions/vs-1/1.webm")
    assert fake_repo.mark_audio_purged.await_count == 2


@pytest.mark.asyncio
async def test_purge_async_no_expired_turns_is_a_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_repo = MagicMock(
        list_with_unpurged_audio_older_than=AsyncMock(return_value=[]),
        mark_audio_purged=AsyncMock(),
    )
    monkeypatch.setattr(
        "app.features.lectures.repository.LectureVoiceTurnRepository", lambda _session: fake_repo
    )
    mock_delete = MagicMock()
    monkeypatch.setattr("app.infrastructure.storage.client.delete_object", mock_delete)

    result = await _purge_expired_voice_audio_async(AsyncMock())

    assert result == {"purged_count": 0}
    mock_delete.assert_not_called()
    fake_repo.mark_audio_purged.assert_not_awaited()
