"""student_question_image retention purge task tests — T-166 / T-170."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.features.student_questions.tasks import (
    _purge_expired_question_images_async,
    purge_expired_question_images,
)


def test_purge_task_delegates_to_run_db() -> None:
    with patch(
        "app.features.student_questions.tasks.run_db", return_value={"purged_count": 2}
    ) as mock_run_db:
        result = purge_expired_question_images()

    assert result == {"purged_count": 2}
    mock_run_db.assert_called_once()


def _fake_record(record_id: str, minio_key: str) -> Any:
    record = MagicMock()
    record.id = record_id
    record.minio_key = minio_key
    record.bucket = "images"
    return record


@pytest.mark.asyncio
async def test_purge_async_deletes_expired_uploads(monkeypatch: pytest.MonkeyPatch) -> None:
    expired = [
        _fake_record("u1", "student-question-image/school-1/2025/01/01/u1/a.jpg"),
        _fake_record("u2", "student-question-image/school-1/2025/01/02/u2/b.png"),
    ]
    monkeypatch.setattr(
        "app.features.student_questions.tasks.list_expired_uploads",
        AsyncMock(return_value=expired),
    )
    purge_calls: list[Any] = []

    async def _fake_purge(_session: Any, record: Any) -> None:
        purge_calls.append(record)

    monkeypatch.setattr(
        "app.features.student_questions.tasks.purge_expired_upload", _fake_purge
    )

    result = await _purge_expired_question_images_async(AsyncMock())

    assert result == {"purged_count": 2}
    assert len(purge_calls) == 2


@pytest.mark.asyncio
async def test_purge_async_no_expired_uploads_is_a_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.features.student_questions.tasks.list_expired_uploads",
        AsyncMock(return_value=[]),
    )
    fake_purge = AsyncMock()
    monkeypatch.setattr("app.features.student_questions.tasks.purge_expired_upload", fake_purge)

    result = await _purge_expired_question_images_async(AsyncMock())

    assert result == {"purged_count": 0}
    fake_purge.assert_not_awaited()


@pytest.mark.asyncio
async def test_purge_uses_365_day_retention_cutoff(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    async def _fake_list(_session: Any, *, profile_name: str, cutoff: Any) -> list[Any]:
        captured["profile_name"] = profile_name
        captured["cutoff"] = cutoff
        return []

    monkeypatch.setattr(
        "app.features.student_questions.tasks.list_expired_uploads", _fake_list
    )
    monkeypatch.setattr(
        "app.features.student_questions.tasks.purge_expired_upload", AsyncMock()
    )

    await _purge_expired_question_images_async(AsyncMock())

    assert captured["profile_name"] == "student_question_image"
