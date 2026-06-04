"""Unit tests for ExamSyllabiService — T-020 acceptance criteria."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import NotFoundError, ValidationError
from app.features.exam_syllabi.models import ExamSyllabus, SyllabusTopic
from app.features.exam_syllabi.schemas import ExamSyllabusCreate, SyllabusTopicCreate
from app.features.exam_syllabi.service import ExamSyllabiService


@pytest.fixture
def mock_session() -> AsyncMock:
    return AsyncMock()


def _make_syllabus(version: int = 1) -> ExamSyllabus:
    """Build an ExamSyllabus instance without touching the DB."""
    return ExamSyllabus(
        id="syllabus-001",
        name="AKU-EB Grade 9 Urdu",
        exam_board="AKU-EB",
        region="Sindh",
        grade_range_min=9,
        grade_range_max=9,
        language="ur",
        version_number=version,
        is_active=True,
        deleted_at=None,
    )


def _make_topic(depth: int = 0) -> SyllabusTopic:
    """Build a SyllabusTopic instance without touching the DB."""
    return SyllabusTopic(
        id="topic-001",
        syllabus_id="syllabus-001",
        parent_id=None,
        title="Chapter 1",
        depth=depth,
        order_index=0,
        deleted_at=None,
    )


@pytest.mark.asyncio
async def test_create_syllabus_sets_version_1(mock_session: AsyncMock) -> None:
    """Newly created syllabi must always start at version_number=1."""
    svc = ExamSyllabiService(mock_session)
    repo_mock = AsyncMock()
    # Capture the syllabus passed to create and return it unchanged
    repo_mock.create.side_effect = lambda s: s
    svc._repo = repo_mock

    payload = ExamSyllabusCreate(
        name="AKU-EB Grade 9 Urdu",
        exam_board="AKU-EB",
        region="Sindh",
        grade_range_min=9,
        grade_range_max=9,
        language="ur",
    )
    result = await svc.create_syllabus(payload, created_by="admin-001")
    assert result.version_number == 1


@pytest.mark.asyncio
async def test_topic_depth_over_4_raises_validation_error(mock_session: AsyncMock) -> None:
    """Creating a child topic under a depth-4 parent must raise ValidationError.

    A depth-4 parent produces depth=5 for the child, which exceeds _MAX_TOPIC_DEPTH=4.
    """
    svc = ExamSyllabiService(mock_session)
    repo_mock = AsyncMock()

    # Syllabus exists
    repo_mock.get_by_id.return_value = _make_syllabus()
    # Parent topic is at depth=4 (the maximum allowed leaf)
    parent_at_depth_4 = _make_topic(depth=4)
    repo_mock.get_topic_by_id.return_value = parent_at_depth_4
    svc._repo = repo_mock

    payload = SyllabusTopicCreate(
        syllabus_id="syllabus-001",
        parent_id="topic-001",
        title="Sub-sub-sub-sub-item",
        order_index=0,
    )
    with pytest.raises(ValidationError):
        await svc.create_topic("syllabus-001", payload)


@pytest.mark.asyncio
async def test_get_missing_syllabus_raises_not_found(mock_session: AsyncMock) -> None:
    """get_syllabus must raise NotFoundError when the repo returns None."""
    svc = ExamSyllabiService(mock_session)
    repo_mock = AsyncMock()
    repo_mock.get_by_id.return_value = None
    svc._repo = repo_mock

    with pytest.raises(NotFoundError):
        await svc.get_syllabus("nonexistent-id")
