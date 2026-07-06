"""Data rights service tests — T-084."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import ConflictError, ValidationError
from app.features.data_rights.models import (
    DataRightsRequest,
    DataRightsRequestStatus,
    DataRightsRequestType,
)
from app.features.data_rights.service import DataRightsService
from app.features.student_onboarding.models import StudentProfile
from app.features.users.models import User, UserAccountStatus, UserRole


class _FakeRequestRepo:
    store: dict[str, DataRightsRequest] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def list_for_user(self, user_id: str) -> list[DataRightsRequest]:
        return [r for r in self.store.values() if r.user_id == user_id]

    async def get_active_export(self, user_id: str) -> DataRightsRequest | None:
        for request in self.store.values():
            if (
                request.user_id == user_id
                and request.request_type == DataRightsRequestType.EXPORT
                and request.status
                in {
                    DataRightsRequestStatus.REQUESTED,
                    DataRightsRequestStatus.PROCESSING,
                    DataRightsRequestStatus.READY,
                }
            ):
                return request
        return None

    async def get_active_deletion(self, user_id: str) -> DataRightsRequest | None:
        for request in self.store.values():
            if (
                request.user_id == user_id
                and request.request_type == DataRightsRequestType.DELETION
                and request.status == DataRightsRequestStatus.GRACE_PERIOD
            ):
                return request
        return None

    async def create(self, request: DataRightsRequest) -> DataRightsRequest:
        self.store[request.id] = request
        return request

    async def get_for_user(self, *, request_id: str, user_id: str) -> DataRightsRequest | None:
        request = self.store.get(request_id)
        if request and request.user_id == user_id:
            return request
        return None

    async def update(self, request: DataRightsRequest) -> DataRightsRequest:
        self.store[request.id] = request
        return request


class _FakeUserRepo:
    store: dict[str, User] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_authentik_id(self, authentik_id: str) -> User | None:
        return next((u for u in self.store.values() if u.authentik_id == authentik_id), None)


class _FakeStudentProfileRepo:
    store: dict[str, StudentProfile] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_user_id(self, user_id: str) -> StudentProfile | None:
        return self.store.get(user_id)


STUDENT = User(
    id="student-1",
    authentik_id="auth-student",
    email="student@example.com",
    display_name="Student One",
    role=UserRole.STUDENT,
    status=UserAccountStatus.ACTIVE,
    school_id="school-1",
)
CLAIMS = {"sub": "auth-student", "role": "student"}


@pytest.fixture(autouse=True)
def _patch_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeRequestRepo.store = {}
    _FakeUserRepo.store = {STUDENT.id: STUDENT}
    _FakeStudentProfileRepo.store = {
        STUDENT.id: StudentProfile(
            user_id=STUDENT.id,
            display_name="Student One",
            language_preference="en",
        )
    }

    monkeypatch.setattr(
        "app.features.data_rights.service.DataRightsRequestRepository", _FakeRequestRepo
    )
    monkeypatch.setattr("app.features.data_rights.service.UserRepository", _FakeUserRepo)
    monkeypatch.setattr(
        "app.features.data_rights.service.StudentProfileRepository", _FakeStudentProfileRepo
    )
    monkeypatch.setattr("app.features.data_rights.service.ParentProfileRepository", MagicMock())
    monkeypatch.setattr("app.features.data_rights.service.ParentChildLinkRepository", MagicMock())
    monkeypatch.setattr("app.features.data_rights.service.StudentEnrollmentRepository", MagicMock())
    monkeypatch.setattr("app.features.data_rights.service.audit", AsyncMock())
    monkeypatch.setattr("app.features.data_rights.service.notify_account_event", AsyncMock())
    monkeypatch.setattr(
        "app.features.data_rights.tasks.process_data_export.delay",
        MagicMock(),
    )


@pytest.mark.asyncio
async def test_request_export_queues_job() -> None:
    session = AsyncMock()
    session.commit = AsyncMock()
    svc = DataRightsService(session)

    result = await svc.request_export(CLAIMS, role=UserRole.STUDENT, actor_id="auth-student")

    assert result.request_type == DataRightsRequestType.EXPORT
    assert result.status == DataRightsRequestStatus.REQUESTED
    assert len(_FakeRequestRepo.store) == 1


@pytest.mark.asyncio
async def test_duplicate_export_rejected() -> None:
    session = AsyncMock()
    session.commit = AsyncMock()
    svc = DataRightsService(session)
    await svc.request_export(CLAIMS, role=UserRole.STUDENT, actor_id="auth-student")

    with pytest.raises(ConflictError):
        await svc.request_export(CLAIMS, role=UserRole.STUDENT, actor_id="auth-student")


@pytest.mark.asyncio
async def test_deletion_requires_confirmation() -> None:
    session = AsyncMock()
    svc = DataRightsService(session)

    with pytest.raises(ValidationError):
        await svc.request_deletion(
            CLAIMS,
            role=UserRole.STUDENT,
            actor_id="auth-student",
            confirmed=False,
        )


@pytest.mark.asyncio
async def test_deletion_enters_grace_period() -> None:
    session = AsyncMock()
    session.commit = AsyncMock()
    svc = DataRightsService(session)

    result = await svc.request_deletion(
        CLAIMS,
        role=UserRole.STUDENT,
        actor_id="auth-student",
        confirmed=True,
    )

    assert result.request_type == DataRightsRequestType.DELETION
    assert result.status == DataRightsRequestStatus.GRACE_PERIOD
    assert result.deletion_scheduled_at is not None
    assert result.deletion_scheduled_at > datetime.now(timezone.utc) + timedelta(days=29)


@pytest.mark.asyncio
async def test_cancel_deletion_during_grace() -> None:
    session = AsyncMock()
    session.commit = AsyncMock()
    svc = DataRightsService(session)
    created = await svc.request_deletion(
        CLAIMS,
        role=UserRole.STUDENT,
        actor_id="auth-student",
        confirmed=True,
    )

    cancelled = await svc.cancel_deletion(
        created.id,
        CLAIMS,
        role=UserRole.STUDENT,
        actor_id="auth-student",
    )

    assert cancelled.status == DataRightsRequestStatus.CANCELLED
    assert cancelled.cancelled_at is not None
