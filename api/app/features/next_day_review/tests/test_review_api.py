"""M-16 review API contract tests — envelope shape, response_model, role floor.

The service is replaced by a recording fake; service behaviour is covered in
the per-ticket service tests.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import date
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1.router import router as v1_router
from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import setup_exception_handlers
from app.features.next_day_review.models import LectureReviewStatus
from app.features.next_day_review.schemas import ReviewDetailRead, ReviewSummaryRead

_SUMMARY: dict[str, Any] = {
    "id": "rev-1",
    "lecture_id": "lec-1",
    "lecture_title": "Newton's Laws",
    "offering_label": "Grade 9 Physics",
    "review_date": date(2026, 10, 22),
    "status": LectureReviewStatus.PENDING,
    "pending_action": True,
    "critical_count": 1,
    "high_frequency_count": 0,
    "read_only": False,
}
_DETAIL = ReviewDetailRead(
    **_SUMMARY,
    ai_summary="Summary.",
    reflective_prompt="Prompt?",
    reflected=False,
    is_owner=True,
    can_act=True,
)


class FakeService:
    calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    def __init__(self, _session: Any) -> None:
        pass

    def __getattr__(self, name: str) -> Any:
        async def _call(*args: Any, **kwargs: Any) -> Any:
            FakeService.calls.append((name, args, kwargs))
            if name == "list_reviews":
                return [ReviewSummaryRead(**_SUMMARY)]
            return _DETAIL

        return _call


@pytest.fixture(autouse=True)
def _fake_service(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeService.calls = []
    monkeypatch.setattr("app.features.next_day_review.router.NextDayReviewService", FakeService)


async def _fake_db() -> AsyncGenerator[None, None]:
    yield None


def _client(role: str) -> AsyncClient:
    async def _claims() -> dict[str, object]:
        return {"sub": f"ak-{role}", "role": role, "school_id": "school-1"}

    app = FastAPI()
    setup_exception_handlers(app)
    app.include_router(v1_router, prefix="/api/v1")
    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_user] = _claims
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_list_reviews_envelope_and_lecture_filter() -> None:
    async with _client("teacher") as client:
        resp = await client.get("/api/v1/reviews", params={"lecture_id": "lec-1"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"][0]["id"] == "rev-1"
    assert body["data"][0]["critical_count"] == 1
    assert FakeService.calls[0][2] == {"lecture_id": "lec-1"}


@pytest.mark.asyncio
async def test_get_review_envelope() -> None:
    async with _client("coordinator") as client:
        resp = await client.get("/api/v1/reviews/rev-1")
    assert resp.status_code == 200
    assert resp.json()["data"]["ai_summary"] == "Summary."


@pytest.mark.asyncio
async def test_student_role_is_forbidden() -> None:
    async with _client("student") as client:
        resp = await client.get("/api/v1/reviews")
    assert resp.status_code == 403
    assert FakeService.calls == []
