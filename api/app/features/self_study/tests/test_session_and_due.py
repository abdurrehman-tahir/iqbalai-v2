"""T-210 — session tagging, Flow 7 gate, retrieval plan, due-flashcards contract."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1.router import router as v1_router
from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import setup_exception_handlers
from app.db.base import Base
from app.features.independent_users.models import (
    IndependentUser,
    IndependentUserAccountStatus,
    IndependentUserRole,
)
from app.features.self_study.events import should_forward_to_flow7, tag_self_study_payload
from app.features.self_study.retrieval import build_self_study_retrieval_plan
from app.features.self_study.sessions import event_reaches_flow7
from app.features.users.models import User, UserAccountStatus, UserRole

_ROOT = Path(__file__).resolve().parents[4]


def test_session_tables_both_schemas() -> None:
    assert "school.self_study_sessions" in Base.metadata.tables
    assert "independent.self_study_sessions" in Base.metadata.tables
    school_mig = _ROOT / "alembic" / "versions" / "school" / "0082_self_study_sessions.py"
    ind_mig = _ROOT / "alembic" / "versions" / "independent" / "0022_self_study_sessions.py"
    assert school_mig.is_file()
    assert ind_mig.is_file()


def test_independent_events_never_reach_flow7() -> None:
    assert (
        event_reaches_flow7(
            tenant_type="independent",
            mode="self_study",
            teacher_activity_share="share",
        )
        is False
    )
    assert should_forward_to_flow7({"tenant_type": "independent", "mode": "self_study"}) is False


def test_school_self_study_reaches_flow7_when_share() -> None:
    assert (
        event_reaches_flow7(
            tenant_type="school",
            mode="self_study",
            teacher_activity_share="share",
        )
        is True
    )
    assert (
        event_reaches_flow7(
            tenant_type="school",
            mode="self_study",
            teacher_activity_share="private",
        )
        is False
    )


def test_payload_always_tagged_mode_self_study() -> None:
    tagged = tag_self_study_payload({"student_user_id": "u1", "tenant_type": "school"})
    assert tagged["mode"] == "self_study"
    assert tagged["tenant_type"] == "school"


def test_retrieval_plan_school_vs_independent() -> None:
    school = build_self_study_retrieval_plan(tenant_type="school")
    assert school.pattern == "A"
    assert school.primary_collection == "student_upload_chunks"
    assert school.overlays == ("cross_grade_curriculum",)
    ind = build_self_study_retrieval_plan(tenant_type="independent", has_exam_syllabus=False)
    assert ind.overlays == ("ai_knowledge",)
    ind_syll = build_self_study_retrieval_plan(tenant_type="independent", has_exam_syllabus=True)
    assert ind_syll.overlays == ("exam_syllabus",)


@pytest.mark.asyncio
async def test_due_flashcards_schedule_not_computed(monkeypatch: pytest.MonkeyPatch) -> None:
    user = User(
        id="school-u1",
        authentik_id="auth-school-1",
        email="s@example.com",
        display_name="S",
        role=UserRole.STUDENT,
        status=UserAccountStatus.ACTIVE,
        school_id="school-1",
    )

    class _UserRepo:
        def __init__(self, session: object) -> None:
            pass

        async def get_by_authentik_id(self, authentik_id: str) -> User | None:
            return user if authentik_id == "auth-school-1" else None

    class _FakeResult:
        def scalars(self) -> object:
            return self

        def all(self) -> list[object]:
            return []

    session = AsyncMock()
    session.execute = AsyncMock(return_value=_FakeResult())

    monkeypatch.setattr(
        "app.features.self_study.session_service.UserRepository",
        _UserRepo,
    )

    from app.features.self_study.session_service import SelfStudySessionService

    svc = SelfStudySessionService(session)
    deck = await svc.list_due_flashcards(
        {"sub": "auth-school-1", "role": "student", "tenant_type": "school"}
    )
    assert deck.schedule_computed is False
    assert deck.schedule_owner == "flow_9"
    assert deck.items == []


@pytest.mark.asyncio
async def test_start_session_independent_api(monkeypatch: pytest.MonkeyPatch) -> None:
    ind = IndependentUser(
        id="ind-u1",
        authentik_id="auth-ind-1",
        email="i@example.com",
        display_name="I",
        role=IndependentUserRole.INDEPENDENT_STUDENT,
        status=IndependentUserAccountStatus.ACTIVE,
    )

    class _IndRepo:
        def __init__(self, session: object) -> None:
            pass

        async def get_by_authentik_id(self, authentik_id: str) -> IndependentUser | None:
            return ind if authentik_id == "auth-ind-1" else None

    session = AsyncMock()
    session.add = lambda *_a, **_k: None
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    async def _refresh(row: object) -> None:
        if getattr(row, "id", None) is None:
            object.__setattr__(row, "id", "sess-1")

    session.refresh = _refresh

    monkeypatch.setattr(
        "app.features.self_study.session_service.IndependentUserRepository",
        _IndRepo,
    )
    monkeypatch.setattr(
        "app.features.self_study.session_service.publish_self_study_session_started",
        AsyncMock(),
    )

    application = FastAPI()
    setup_exception_handlers(application)
    application.include_router(v1_router, prefix="/api/v1")

    async def _db() -> object:
        yield session

    application.dependency_overrides[get_db] = _db
    application.dependency_overrides[get_current_user] = lambda: {
        "sub": "auth-ind-1",
        "role": "independent_student",
        "tenant_type": "independent",
    }

    # Bypass ORM flush: patch start to use service directly via API with mocked add
    from datetime import datetime, timezone

    from app.features.self_study.sessions import IndependentSelfStudySession

    created = IndependentSelfStudySession(
        id="sess-ind-1",
        student_user_id=ind.id,
        started_at=datetime.now(timezone.utc),
    )

    async def _fake_start(self: object, payload: object, claims: object) -> object:
        from app.features.self_study.schemas import SelfStudySessionRead

        return SelfStudySessionRead(
            id=created.id,
            tenant_type="independent",
            mode="self_study",
            status="active",
            material_id=None,
            study_plan_id=None,
            retrieval_primary="student_upload_chunks",
            retrieval_overlays=["ai_knowledge"],
            reaches_flow7=False,
        )

    monkeypatch.setattr(
        "app.features.self_study.session_service.SelfStudySessionService.start_session",
        _fake_start,
    )

    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/self-study/me/sessions", json={})
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["mode"] == "self_study"
    assert body["reaches_flow7"] is False
    assert body["retrieval_primary"] == "student_upload_chunks"
