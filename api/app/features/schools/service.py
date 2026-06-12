"""District service — business logic for Platform-Admin district management (T-029).

Every mutation is audit-logged (ARCH §14.10). District names are globally unique
(``districts_name_uq``); the service surfaces a duplicate as a ``ConflictError``
rather than letting the DB IntegrityError bubble up.
"""

from __future__ import annotations

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.features.schools.models import District
from app.features.schools.repository import DistrictRepository
from app.features.schools.schemas import DistrictCreate, DistrictUpdate
from app.infrastructure.audit.log import audit

logger = structlog.get_logger(__name__)


class DistrictService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = DistrictRepository(session)

    async def list_districts(self) -> list[District]:
        """List all active (non-deleted) districts."""
        return await self._repo.list_districts()

    async def get_district(self, id: str) -> District:
        """Fetch a district by ID; raise NotFoundError if missing or soft-deleted."""
        district = await self._repo.get_by_id(id)
        if district is None or district.deleted_at is not None:
            raise NotFoundError(f"District '{id}' not found")
        return district

    async def create_district(self, payload: DistrictCreate, actor_id: str) -> District:
        """Create a new district. Rejects a duplicate (active) name with ConflictError."""
        existing = await self._repo.get_active_by_name(payload.name)
        if existing is not None:
            raise ConflictError(f"A district named '{payload.name}' already exists")

        district = District(
            name=payload.name,
            region=payload.region,
            language_preference=payload.language_preference,
        )
        created = await self._repo.create(district)
        await audit(
            session=self._session,
            action="district.created",
            actor_id=actor_id,
            target_type="district",
            target_id=created.id,
            district_id=created.id,
            metadata={"name": created.name, "region": created.region},
        )
        logger.info("district_created", district_id=created.id, name=created.name, by=actor_id)
        return created

    async def update_district(self, id: str, payload: DistrictUpdate, actor_id: str) -> District:
        """Update a district's mutable fields. Rejects a duplicate name with ConflictError."""
        district = await self.get_district(id)

        if payload.name is not None and payload.name != district.name:
            clash = await self._repo.get_active_by_name(payload.name)
            if clash is not None:
                raise ConflictError(f"A district named '{payload.name}' already exists")
            district.name = payload.name
        if payload.region is not None:
            district.region = payload.region
        if payload.language_preference is not None:
            district.language_preference = payload.language_preference

        updated = await self._repo.update(district)
        await audit(
            session=self._session,
            action="district.updated",
            actor_id=actor_id,
            target_type="district",
            target_id=updated.id,
            district_id=updated.id,
            metadata={"name": updated.name},
        )
        logger.info("district_updated", district_id=updated.id, by=actor_id)
        return updated

    async def delete_district(self, id: str, actor_id: str) -> None:
        """Soft-delete a district."""
        district = await self.get_district(id)
        await self._repo.soft_delete(district)
        await audit(
            session=self._session,
            action="district.deleted",
            actor_id=actor_id,
            target_type="district",
            target_id=id,
            district_id=id,
            metadata={"name": district.name},
        )
        logger.info("district_deleted", district_id=id, by=actor_id)
