"""Service-layer invariant tests (T-230).

Exercises the business rules that live above the DB constraints, using in-memory
fake repositories (no DB, no session). These guard the invariants the schema
alone can't express: topic-depth ceiling, monotonic ToS/Disclaimer versioning,
the disclaimer length cap, and double-accept rejection.
"""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import ConflictError, ValidationError
from app.features.exam_syllabi.models import ExamSyllabus, SyllabusTopic
from app.features.exam_syllabi.schemas import SyllabusTopicCreate
from app.features.exam_syllabi.service import ExamSyllabiService
from app.features.tos.models import TosVersion
from app.features.tos.service import TosService

# ── Exam syllabi: topic depth ceiling ──────────────────────────────────────────


class _FakeSyllabiRepo:
    def __init__(self, parent: SyllabusTopic | None) -> None:
        self._parent = parent
        self.created: SyllabusTopic | None = None

    async def get_by_id(self, id: str) -> ExamSyllabus:
        return ExamSyllabus(id=id, name="S", exam_board="B")

    async def get_topic_by_id(self, id: str) -> SyllabusTopic | None:
        return self._parent

    async def create_topic(self, topic: SyllabusTopic) -> SyllabusTopic:
        self.created = topic
        return topic


def _syllabi_service(repo: _FakeSyllabiRepo) -> ExamSyllabiService:
    svc = ExamSyllabiService(session=cast(Any, None))
    svc._repo = cast(Any, repo)
    return svc


@pytest.mark.asyncio
async def test_create_topic_rejects_depth_over_max() -> None:
    # parent already at the max depth (4) → child would be depth 5 → rejected.
    parent = SyllabusTopic(id="p", syllabus_id="s", title="deep", depth=4)
    svc = _syllabi_service(_FakeSyllabiRepo(parent))
    with pytest.raises(ValidationError):
        await svc.create_topic(
            "s", SyllabusTopicCreate(syllabus_id="s", parent_id="p", title="x", order_index=0)
        )


@pytest.mark.asyncio
async def test_create_topic_allows_within_depth() -> None:
    parent = SyllabusTopic(id="p", syllabus_id="s", title="ch", depth=0)
    repo = _FakeSyllabiRepo(parent)
    svc = _syllabi_service(repo)
    created = await svc.create_topic(
        "s", SyllabusTopicCreate(syllabus_id="s", parent_id="p", title="sec", order_index=0)
    )
    assert created.depth == 1


# ── ToS / Disclaimer versioning + acceptance ────────────────────────────────────


class _FakeTosRepo:
    def __init__(self, current: TosVersion | None, already_accepted: bool = False) -> None:
        self._current = current
        self._already = already_accepted

    async def get_current_tos(self) -> TosVersion | None:
        return self._current

    async def create_tos_version(self, tos: TosVersion) -> TosVersion:
        return tos

    async def get_tos_by_id(self, tos_version_id: str) -> TosVersion | None:
        return self._current

    async def has_accepted_tos(self, user_id: str, tos_version_id: str) -> bool:
        return self._already

    async def record_acceptance(self, user_id: str, tos_version_id: str, ip: str | None) -> object:
        return object()


def _tos_service(repo: _FakeTosRepo) -> TosService:
    svc = TosService(session=cast(Any, None))
    svc._repo = cast(Any, repo)
    return svc


@pytest.mark.asyncio
async def test_publish_tos_increments_version() -> None:
    current = TosVersion(id="t3", version_number=3, content_md="...", effective_at=None)
    svc = _tos_service(_FakeTosRepo(current))
    with patch("app.features.tos.service.audit", new_callable=AsyncMock):
        created = await svc.publish_new_tos(content_md="new", language="en", published_by="admin")
    assert created.version_number == 4


@pytest.mark.asyncio
async def test_publish_first_tos_starts_at_one() -> None:
    svc = _tos_service(_FakeTosRepo(None))
    with patch("app.features.tos.service.audit", new_callable=AsyncMock):
        created = await svc.publish_new_tos(content_md="first", language="en", published_by="admin")
    assert created.version_number == 1


@pytest.mark.asyncio
async def test_accept_tos_twice_conflicts() -> None:
    current = TosVersion(id="t1", version_number=1, content_md="...", effective_at=None)
    svc = _tos_service(_FakeTosRepo(current, already_accepted=True))
    with pytest.raises(ConflictError):
        await svc.accept_tos(user_id="u1", tos_version_id="t1")


@pytest.mark.asyncio
async def test_publish_disclaimer_rejects_over_500_chars() -> None:
    svc = _tos_service(_FakeTosRepo(None))
    with pytest.raises(ValidationError):
        await svc.publish_new_disclaimer(content="x" * 501, language="en", published_by="admin")
