"""Parent-side parent-child link endpoints — T-081."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.core.responses import SuccessEnvelope, success
from app.features.parent_child_links.schemas import (
    ParentChildLinkRead,
    ParentConnectionsRead,
    ParentLinkRequestCreate,
)
from app.features.parent_child_links.service import ParentChildLinkService

router = APIRouter(prefix="/parents/me", tags=["parent-links"])


@router.get(
    "/connections",
    response_model=SuccessEnvelope[ParentConnectionsRead],
    operation_id="parent_get_connections",
    summary="List parent link requests and linked children",
    dependencies=[require_role("parent")],
)
async def get_parent_connections(
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = ParentChildLinkService(db)
    result = await svc.get_parent_connections(claims)
    return success(result.model_dump())


@router.post(
    "/link-requests",
    response_model=SuccessEnvelope[ParentChildLinkRead],
    operation_id="parent_create_link_request",
    status_code=201,
    summary="Request a link to a school student by email",
    dependencies=[require_role("parent")],
)
async def create_link_request(
    payload: ParentLinkRequestCreate,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = ParentChildLinkService(db)
    result = await svc.create_link_request(payload, claims)
    return success(result.model_dump())
