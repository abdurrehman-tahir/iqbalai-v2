"""Independent private pool router — T-074."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, Query, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.responses import SuccessEnvelope, success
from app.features.library.independent_personal_schemas import (
    IndependentPersonalContentRead,
    IndependentPersonalListResponse,
    IndependentPersonalUploadRequest,
    IndependentPersonalUploadResponse,
)
from app.features.library.independent_personal_service import IndependentPersonalContentService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/independent/personal-content", tags=["independent-personal-content"])


@router.post(
    "/",
    response_model=SuccessEnvelope[IndependentPersonalUploadResponse],
    operation_id="independent_personal_content_upload",
    status_code=202,
    summary="Upload a PDF to the independent private pool",
    description=(
        "Accepts a PDF via the independent_personal_content profile (100 MB, per-user dedup). "
        "Content is always private to the uploading user."
    ),
)
async def upload_independent_personal_content(
    file: UploadFile,
    title: str = Query(..., min_length=1, max_length=500),
    content_type: str = Query(default="reference", pattern="^(curriculum|reference)$"),
    language: str = Query(default="en", pattern="^(en|ur|sd|ps)$"),
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    data = await file.read()
    meta = IndependentPersonalUploadRequest(
        title=title,
        content_type=content_type,
        language=language,
    )
    svc = IndependentPersonalContentService(db)
    result = await svc.upload(
        data=data,
        filename=file.filename or "upload.pdf",
        meta=meta,
        authentik_id=str(claims.get("sub", "")),
    )
    logger.info("independent_personal_upload_endpoint", content_id=result.item.id)
    return JSONResponse(status_code=202, content=success(result.model_dump(mode="json")))


@router.get(
    "/",
    response_model=SuccessEnvelope[IndependentPersonalListResponse],
    operation_id="independent_personal_content_list",
    summary="List the caller's private pool items",
)
async def list_independent_personal_content(
    content_type: str | None = Query(default=None, pattern="^(curriculum|reference)$"),
    title: str | None = Query(default=None, max_length=500),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessEnvelope[IndependentPersonalListResponse]:
    svc = IndependentPersonalContentService(db)
    result = await svc.list_items(
        claims,
        content_type=content_type,
        title=title,
        limit=limit,
        offset=offset,
    )
    return success(result.model_dump(mode="json"))


@router.get(
    "/{content_id}",
    response_model=SuccessEnvelope[IndependentPersonalContentRead],
    operation_id="independent_personal_content_get",
    summary="Get a private pool item owned by the caller",
)
async def get_independent_personal_content(
    content_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessEnvelope[IndependentPersonalContentRead]:
    svc = IndependentPersonalContentService(db)
    item = await svc.get_item(content_id, claims)
    return success(item.model_dump(mode="json"))
