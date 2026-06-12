"""Unit tests for DistrictService — T-029 acceptance criteria.

Service-level tests with a mocked repository (the established pattern in this repo):
happy paths for create/list/update/soft-delete plus the failure modes — duplicate
name (ConflictError) and missing district (NotFoundError). Audit writes are patched to
a no-op so these stay pure unit tests.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import ConflictError, NotFoundError
from app.features.schools.models import District
from app.features.schools.schemas import DistrictCreate, DistrictUpdate
from app.features.schools.service import DistrictService


@pytest.fixture
def mock_session() -> AsyncMock:
    return AsyncMock()


@pytest.fixture(autouse=True)
def _no_audit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch the audit writer so service tests don't touch the audit_log table."""
    monkeypatch.setattr("app.features.schools.service.audit", AsyncMock(return_value=None))


def _make_district(name: str = "Lahore District") -> District:
    """Build a District instance without touching the DB."""
    return District(
        id="district-001",
        name=name,
        region="Punjab",
        language_preference="ur",
        deleted_at=None,
    )


async def test_create_district_persists_fields(mock_session: AsyncMock) -> None:
    """A created district carries through name/region/language_preference."""
    svc = DistrictService(mock_session)
    repo = AsyncMock()
    repo.get_active_by_name.return_value = None
    repo.create.side_effect = lambda d: d
    svc._repo = repo

    payload = DistrictCreate(name="Karachi District", region="Sindh", language_preference="en")
    created = await svc.create_district(payload, actor_id="admin-1")

    assert created.name == "Karachi District"
    assert created.region == "Sindh"
    assert created.language_preference == "en"
    repo.create.assert_awaited_once()


async def test_create_district_rejects_duplicate_name(mock_session: AsyncMock) -> None:
    """Creating a district whose name already exists raises ConflictError."""
    svc = DistrictService(mock_session)
    repo = AsyncMock()
    repo.get_active_by_name.return_value = _make_district("Lahore District")
    svc._repo = repo

    with pytest.raises(ConflictError):
        await svc.create_district(DistrictCreate(name="Lahore District"), actor_id="admin-1")
    repo.create.assert_not_awaited()


async def test_create_district_allows_name_after_soft_delete(mock_session: AsyncMock) -> None:
    """A soft-deleted district name can be reused for a new district."""
    svc = DistrictService(mock_session)
    repo = AsyncMock()
    repo.get_active_by_name.return_value = None
    repo.create.side_effect = lambda d: d
    svc._repo = repo

    created = await svc.create_district(DistrictCreate(name="mansehra"), actor_id="admin-1")

    assert created.name == "mansehra"
    repo.create.assert_awaited_once()


async def test_get_district_missing_raises_not_found(mock_session: AsyncMock) -> None:
    """Fetching an unknown id raises NotFoundError."""
    svc = DistrictService(mock_session)
    repo = AsyncMock()
    repo.get_by_id.return_value = None
    svc._repo = repo

    with pytest.raises(NotFoundError):
        await svc.get_district("nope")


async def test_get_district_soft_deleted_raises_not_found(mock_session: AsyncMock) -> None:
    """A soft-deleted district is treated as not found."""
    from datetime import datetime, timezone

    svc = DistrictService(mock_session)
    deleted = _make_district()
    deleted.deleted_at = datetime.now(timezone.utc)
    repo = AsyncMock()
    repo.get_by_id.return_value = deleted
    svc._repo = repo

    with pytest.raises(NotFoundError):
        await svc.get_district("district-001")


async def test_update_district_changes_fields(mock_session: AsyncMock) -> None:
    """Update applies only the provided fields and returns the updated row."""
    svc = DistrictService(mock_session)
    existing = _make_district()
    repo = AsyncMock()
    repo.get_by_id.return_value = existing
    repo.get_active_by_name.return_value = None
    repo.update.side_effect = lambda d: d
    svc._repo = repo

    updated = await svc.update_district(
        "district-001", DistrictUpdate(region="Islamabad"), actor_id="admin-1"
    )
    assert updated.region == "Islamabad"
    assert updated.name == "Lahore District"  # unchanged


async def test_update_district_rejects_duplicate_name(mock_session: AsyncMock) -> None:
    """Renaming to an existing district's name raises ConflictError."""
    svc = DistrictService(mock_session)
    existing = _make_district("Lahore District")
    repo = AsyncMock()
    repo.get_by_id.return_value = existing
    repo.get_active_by_name.return_value = _make_district("Karachi District")
    svc._repo = repo

    with pytest.raises(ConflictError):
        await svc.update_district(
            "district-001", DistrictUpdate(name="Karachi District"), actor_id="admin-1"
        )
    repo.update.assert_not_awaited()


async def test_delete_district_soft_deletes(mock_session: AsyncMock) -> None:
    """Delete resolves the district then calls the repo soft-delete."""
    svc = DistrictService(mock_session)
    existing = _make_district()
    repo = AsyncMock()
    repo.get_by_id.return_value = existing
    svc._repo = repo

    await svc.delete_district("district-001", actor_id="admin-1")
    repo.soft_delete.assert_awaited_once_with(existing)


async def test_list_districts_delegates_to_repo(mock_session: AsyncMock) -> None:
    """List returns whatever the repo returns."""
    svc = DistrictService(mock_session)
    repo = AsyncMock()
    repo.list_districts.return_value = [_make_district()]
    svc._repo = repo

    result = await svc.list_districts()
    assert len(result) == 1
    assert result[0].name == "Lahore District"
