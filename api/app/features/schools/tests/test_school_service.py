"""Unit tests for SchoolService — T-031."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import ConflictError, NotFoundError
from app.features.schools.models import District, School
from app.features.schools.schemas import SchoolCreate, SchoolUpdate
from app.features.schools.service import SchoolService


@pytest.fixture
def mock_session() -> AsyncMock:
    return AsyncMock()


@pytest.fixture(autouse=True)
def _no_audit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.features.schools.service.audit", AsyncMock(return_value=None))


def _district(id: str = "dist-1") -> District:
    return District(id=id, name="Punjab District 1", region="Punjab")


def _school(district_id: str = "dist-1", name: str = "Sample School") -> School:
    return School(id="school-1", district_id=district_id, name=name, deleted_at=None)


def _claims(role: str = "district_admin", district_id: str = "dist-1") -> dict[str, object]:
    return {"sub": "da-1", "role": role, "district_id": district_id}


async def test_create_school_persists_fields(mock_session: AsyncMock) -> None:
    svc = SchoolService(mock_session)
    repo = AsyncMock()
    districts = AsyncMock()
    districts.get_by_id.return_value = _district()
    repo.get_active_by_name_in_district.return_value = None
    repo.create.side_effect = lambda s: s
    svc._repo = repo
    svc._districts = districts

    created = await svc.create_school(
        SchoolCreate(name="Sample School", district_id="dist-1"),
        actor_id="da-1",
        claims=_claims(),
        caller_role="district_admin",
    )
    assert created.name == "Sample School"
    assert created.district_id == "dist-1"
    repo.create.assert_awaited_once()


async def test_create_school_rejects_duplicate_name(mock_session: AsyncMock) -> None:
    svc = SchoolService(mock_session)
    repo = AsyncMock()
    districts = AsyncMock()
    districts.get_by_id.return_value = _district()
    repo.get_active_by_name_in_district.return_value = _school()
    svc._repo = repo
    svc._districts = districts

    with pytest.raises(ConflictError):
        await svc.create_school(
            SchoolCreate(name="Sample School", district_id="dist-1"),
            actor_id="da-1",
            claims=_claims(),
            caller_role="district_admin",
        )


async def test_cross_district_get_returns_404(mock_session: AsyncMock) -> None:
    svc = SchoolService(mock_session)
    repo = AsyncMock()
    repo.get_by_id.return_value = _school(district_id="dist-other")
    svc._repo = repo

    with pytest.raises(NotFoundError):
        await svc.get_school("school-1", _claims(district_id="dist-1"), "district_admin")


async def test_platform_admin_can_access_any_district(mock_session: AsyncMock) -> None:
    svc = SchoolService(mock_session)
    repo = AsyncMock()
    repo.get_by_id.return_value = _school(district_id="dist-other")
    svc._repo = repo

    school = await svc.get_school(
        "school-1", {"sub": "pa-1", "role": "platform_admin"}, "platform_admin"
    )
    assert school.district_id == "dist-other"


async def test_list_scoped_to_caller_district(mock_session: AsyncMock) -> None:
    svc = SchoolService(mock_session)
    repo = AsyncMock()
    repo.list_schools.return_value = [_school()]
    svc._repo = repo

    result = await svc.list_schools(_claims(), "district_admin")
    assert len(result) == 1
    repo.list_schools.assert_awaited_once_with(district_id="dist-1")


async def test_update_school_changes_name(mock_session: AsyncMock) -> None:
    svc = SchoolService(mock_session)
    existing = _school()
    repo = AsyncMock()
    repo.get_by_id.return_value = existing
    repo.get_active_by_name_in_district.return_value = None
    repo.update.side_effect = lambda s: s
    svc._repo = repo

    updated = await svc.update_school(
        "school-1",
        SchoolUpdate(name="Renamed School"),
        actor_id="da-1",
        claims=_claims(),
        caller_role="district_admin",
    )
    assert updated.name == "Renamed School"


async def test_delete_school_soft_deletes(mock_session: AsyncMock) -> None:
    svc = SchoolService(mock_session)
    existing = _school()
    repo = AsyncMock()
    repo.get_by_id.return_value = existing
    svc._repo = repo

    await svc.delete_school("school-1", "da-1", _claims(), "district_admin")
    repo.soft_delete.assert_awaited_once_with(existing)
