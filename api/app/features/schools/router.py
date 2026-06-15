"""District API endpoints — T-029 (Platform Admin only).

Districts are the org-hierarchy root (ARCH §3.3); only a Platform Admin may manage
them, so every route requires the ``platform_admin`` role. The create route accepts
an ``Idempotency-Key`` header (ARCH §5.9) so a retried POST never creates a duplicate
district.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.core.idempotency import IdempotencyContext, idempotency_key
from app.core.responses import success
from app.features.schools.schemas import DistrictCreate, DistrictRead, DistrictUpdate
from app.features.schools.service import DistrictService

router = APIRouter(prefix="/admin/districts", tags=["districts"])


@router.get(
    "/",
    response_model=dict,
    summary="List all districts",
    operation_id="districts_list",
    dependencies=[require_role("platform_admin")],
)
async def list_districts(db: AsyncSession = Depends(get_db)) -> dict:
    svc = DistrictService(db)
    districts = await svc.list_districts()
    return success([DistrictRead.model_validate(d).model_dump() for d in districts])


@router.post(
    "/",
    response_model=dict,
    summary="Create a new district",
    operation_id="districts_create",
    status_code=201,
    dependencies=[require_role("platform_admin")],
)
async def create_district(
    payload: DistrictCreate,
    claims: dict = Depends(get_current_user),
    idem: IdempotencyContext | None = Depends(idempotency_key),
    db: AsyncSession = Depends(get_db),
) -> dict:
    # On an idempotent replay (same key + same body) return the cached response
    # without re-creating the district.
    if idem is not None:
        cached = await idem.cached_response()
        if cached is not None:
            return cached

    svc = DistrictService(db)
    district = await svc.create_district(payload, actor_id=str(claims.get("sub", "")))
    # mode="json" keeps the response JSON-serialisable so it can be cached for an
    # idempotent replay (datetimes become ISO strings — identical on the wire to the
    # non-idempotent path, which FastAPI json-encodes anyway).
    response = success(DistrictRead.model_validate(district).model_dump(mode="json"))

    if idem is not None:
        await idem.store_response(response)
    return response


@router.get(
    "/{district_id}",
    response_model=dict,
    summary="Get a single district",
    operation_id="districts_get",
    dependencies=[require_role("platform_admin")],
)
async def get_district(district_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    svc = DistrictService(db)
    district = await svc.get_district(district_id)
    return success(DistrictRead.model_validate(district).model_dump())


@router.put(
    "/{district_id}",
    response_model=dict,
    summary="Update a district",
    operation_id="districts_update",
    dependencies=[require_role("platform_admin")],
)
async def update_district(
    district_id: str,
    payload: DistrictUpdate,
    claims: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    svc = DistrictService(db)
    district = await svc.update_district(district_id, payload, actor_id=str(claims.get("sub", "")))
    return success(DistrictRead.model_validate(district).model_dump())


@router.delete(
    "/{district_id}",
    response_model=dict,
    summary="Soft-delete a district",
    operation_id="districts_delete",
    dependencies=[require_role("platform_admin")],
)
async def delete_district(
    district_id: str,
    claims: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    svc = DistrictService(db)
    await svc.delete_district(district_id, actor_id=str(claims.get("sub", "")))
    return success({"deleted": True})
