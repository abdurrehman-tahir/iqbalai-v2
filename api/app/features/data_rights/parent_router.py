"""Parent data rights endpoints — T-084."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.core.responses import SuccessEnvelope, success
from app.features.data_rights.schemas import (
    DataRightsDeletionCreate,
    DataRightsRequestRead,
    DataRightsStatusRead,
)
from app.features.data_rights.service import DataRightsService
from app.features.users.models import UserRole

router = APIRouter(prefix="/parents/me/data-rights", tags=["data-rights"])


@router.get(
    "",
    response_model=SuccessEnvelope[DataRightsStatusRead],
    operation_id="parent_get_data_rights",
    summary="Get parent data-rights status",
    dependencies=[require_role("parent")],
)
async def get_data_rights(
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = DataRightsService(db)
    status = await svc.get_status(claims, role=UserRole.PARENT)
    return success(status.model_dump())


@router.post(
    "/export",
    response_model=SuccessEnvelope[DataRightsRequestRead],
    operation_id="parent_request_data_export",
    status_code=201,
    summary="Request a personal data export",
    dependencies=[require_role("parent")],
)
async def request_export(
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = DataRightsService(db)
    result = await svc.request_export(
        claims,
        role=UserRole.PARENT,
        actor_id=str(claims.get("sub", "")),
    )
    return success(result.model_dump())


@router.get(
    "/export/{request_id}/download",
    operation_id="parent_download_data_export",
    summary="Download a ready personal data export",
    dependencies=[require_role("parent")],
)
async def download_export(
    request_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    svc = DataRightsService(db)
    data, filename = await svc.download_export(
        request_id,
        claims,
        role=UserRole.PARENT,
    )
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post(
    "/deletion",
    response_model=SuccessEnvelope[DataRightsRequestRead],
    operation_id="parent_request_account_deletion",
    status_code=201,
    summary="Submit an account deletion request (30-day grace, queued for review)",
    dependencies=[require_role("parent")],
)
async def request_deletion(
    payload: DataRightsDeletionCreate,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = DataRightsService(db)
    result = await svc.request_deletion(
        claims,
        role=UserRole.PARENT,
        actor_id=str(claims.get("sub", "")),
        confirmed=payload.confirm,
    )
    return success(result.model_dump())


@router.post(
    "/deletion/{request_id}/cancel",
    response_model=SuccessEnvelope[DataRightsRequestRead],
    operation_id="parent_cancel_account_deletion",
    summary="Cancel a deletion request during the grace period",
    dependencies=[require_role("parent")],
)
async def cancel_deletion(
    request_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = DataRightsService(db)
    result = await svc.cancel_deletion(
        request_id,
        claims,
        role=UserRole.PARENT,
        actor_id=str(claims.get("sub", "")),
    )
    return success(result.model_dump())
