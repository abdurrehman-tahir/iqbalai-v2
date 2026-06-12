"""District service — business logic for Platform-Admin district management (T-029).

Every mutation is audit-logged (ARCH §14.10). District names are globally unique
(``districts_name_uq``); the service surfaces a duplicate as a ``ConflictError``
rather than letting the DB IntegrityError bubble up.
"""

from __future__ import annotations

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import ROLE_HIERARCHY
from app.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError
from app.features.schools.models import District, School
from app.features.schools.repository import DistrictRepository, SchoolRepository
from app.features.schools.schemas import DistrictCreate, DistrictUpdate, SchoolCreate, SchoolUpdate
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


def _caller_district_id(claims: dict[str, object]) -> str | None:
    raw = claims.get("district_id")
    if raw is None or raw == "":
        return None
    return str(raw)


def _is_platform_admin(caller_role: str) -> bool:
    return ROLE_HIERARCHY.get(caller_role, 0) >= ROLE_HIERARCHY["platform_admin"]


class SchoolService:
    """Business logic for District-Admin school management (T-031).

    Cross-district access is deliberately surfaced as ``NotFoundError`` (404) per
    flow-2 §5.6 — not ``PermissionDeniedError`` — so callers cannot probe other
    tenants' resource IDs.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = SchoolRepository(session)
        self._districts = DistrictRepository(session)

    def _assert_district_scope(
        self, claims: dict[str, object], district_id: str, caller_role: str
    ) -> None:
        if _is_platform_admin(caller_role):
            return
        caller_district = _caller_district_id(claims)
        if caller_district != district_id:
            raise NotFoundError("School not found")

    async def _get_district_or_404(self, district_id: str) -> District:
        district = await self._districts.get_by_id(district_id)
        if district is None or district.deleted_at is not None:
            raise NotFoundError(f"District '{district_id}' not found")
        return district

    async def list_schools(
        self, claims: dict[str, object], caller_role: str, district_id: str | None = None
    ) -> list[School]:
        if _is_platform_admin(caller_role):
            return await self._repo.list_schools(district_id=district_id)

        caller_district = _caller_district_id(claims)
        if caller_district is None:
            raise PermissionDeniedError("District scope required")
        if district_id is not None and district_id != caller_district:
            raise NotFoundError("School not found")
        return await self._repo.list_schools(district_id=caller_district)

    async def get_school(
        self, school_id: str, claims: dict[str, object], caller_role: str
    ) -> School:
        school = await self._repo.get_by_id(school_id)
        if school is None or school.deleted_at is not None:
            raise NotFoundError(f"School '{school_id}' not found")
        self._assert_district_scope(claims, school.district_id, caller_role)
        return school

    async def create_school(
        self,
        payload: SchoolCreate,
        actor_id: str,
        claims: dict[str, object],
        caller_role: str,
    ) -> School:
        await self._get_district_or_404(payload.district_id)
        self._assert_district_scope(claims, payload.district_id, caller_role)

        existing = await self._repo.get_active_by_name_in_district(
            payload.district_id, payload.name
        )
        if existing is not None:
            raise ConflictError(f"A school named '{payload.name}' already exists in this district")

        school = School(district_id=payload.district_id, name=payload.name)
        created = await self._repo.create(school)
        await audit(
            session=self._session,
            action="school.created",
            actor_id=actor_id,
            target_type="school",
            target_id=created.id,
            district_id=created.district_id,
            school_id=created.id,
            metadata={"name": created.name, "district_id": created.district_id},
        )
        logger.info(
            "school_created",
            school_id=created.id,
            district_id=created.district_id,
            by=actor_id,
        )
        return created

    async def update_school(
        self,
        school_id: str,
        payload: SchoolUpdate,
        actor_id: str,
        claims: dict[str, object],
        caller_role: str,
    ) -> School:
        school = await self.get_school(school_id, claims, caller_role)

        if payload.name is not None and payload.name != school.name:
            clash = await self._repo.get_active_by_name_in_district(
                school.district_id, payload.name
            )
            if clash is not None:
                raise ConflictError(
                    f"A school named '{payload.name}' already exists in this district"
                )
            school.name = payload.name

        updated = await self._repo.update(school)
        await audit(
            session=self._session,
            action="school.updated",
            actor_id=actor_id,
            target_type="school",
            target_id=updated.id,
            district_id=updated.district_id,
            school_id=updated.id,
            metadata={"name": updated.name},
        )
        logger.info("school_updated", school_id=updated.id, by=actor_id)
        return updated

    async def delete_school(
        self,
        school_id: str,
        actor_id: str,
        claims: dict[str, object],
        caller_role: str,
    ) -> None:
        school = await self.get_school(school_id, claims, caller_role)
        await self._repo.soft_delete(school)
        await audit(
            session=self._session,
            action="school.deleted",
            actor_id=actor_id,
            target_type="school",
            target_id=school_id,
            district_id=school.district_id,
            school_id=school_id,
            metadata={"name": school.name},
        )
        logger.info("school_deleted", school_id=school_id, by=actor_id)
