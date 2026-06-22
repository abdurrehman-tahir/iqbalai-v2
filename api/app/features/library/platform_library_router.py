"""Platform Library read-only router — T-073."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.responses import SuccessEnvelope, success
from app.features.library.platform_library_service import PlatformLibraryReadService
from app.features.library.schemas import LibraryBookListResponse, LibraryBookRead

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/platform/library", tags=["platform-library"])


@router.get(
    "/",
    response_model=SuccessEnvelope[LibraryBookListResponse],
    operation_id="platform_library_list_books",
    summary="List platform library books (read-only)",
    description=(
        "Returns platform-tier reference books visible to all authenticated tenants. "
        "School and independent users share read-only access; only Platform Admin can upload."
    ),
)
async def list_platform_library_books(
    content_type: str | None = Query(default=None, pattern="^(curriculum|reference)$"),
    language: str | None = Query(default=None, pattern="^(en|ur|sd|ps)$"),
    subject_tag: str | None = Query(default=None, max_length=255),
    title: str | None = Query(default=None, max_length=500),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessEnvelope[LibraryBookListResponse]:
    svc = PlatformLibraryReadService(db)
    result = await svc.list_books(
        claims,
        limit=limit,
        offset=offset,
        content_type=content_type,
        language=language,
        subject_tag=subject_tag,
        title=title,
    )
    return success(result.model_dump())


@router.get(
    "/{book_id}",
    response_model=SuccessEnvelope[LibraryBookRead],
    operation_id="platform_library_get_book",
    summary="Get a platform library book (read-only)",
)
async def get_platform_library_book(
    book_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessEnvelope[LibraryBookRead]:
    svc = PlatformLibraryReadService(db)
    book = await svc.get_book(book_id, claims)
    return success(book.model_dump())
