"""Platform Library read-only service — T-073."""

from __future__ import annotations

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.tenant import TenantType, get_tenant_type
from app.features.library.repository import LibraryRepository
from app.features.library.schemas import LibraryBookListResponse, LibraryBookRead

logger = structlog.get_logger(__name__)


class PlatformLibraryReadService:
    """Browse platform library items for any authenticated tenant (read-only)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = LibraryRepository(session)

    async def list_books(
        self,
        claims: dict[str, object],
        *,
        limit: int = 50,
        offset: int = 0,
        content_type: str | None = None,
        language: str | None = None,
        subject_tag: str | None = None,
        title: str | None = None,
    ) -> LibraryBookListResponse:
        tenant_type: TenantType = get_tenant_type(claims)
        books = await self._repo.list_active_for_tenant(
            tenant_type,
            limit=limit,
            offset=offset,
            content_type=content_type,
            language=language,
            subject_tag=subject_tag,
            title=title,
        )
        total = await self._repo.count_active_for_tenant(
            tenant_type,
            content_type=content_type,
            language=language,
            subject_tag=subject_tag,
            title=title,
        )
        logger.info(
            "platform_library_list",
            tenant_type=tenant_type,
            count=len(books),
            total=total,
        )
        return LibraryBookListResponse(
            items=[LibraryBookRead.model_validate(b) for b in books],
            total=total,
        )

    async def get_book(self, book_id: str, claims: dict[str, object]) -> LibraryBookRead:
        tenant_type: TenantType = get_tenant_type(claims)
        book = await self._repo.get_by_id_for_tenant(book_id, tenant_type)
        if book is None:
            raise NotFoundError("Platform library book not found")
        return LibraryBookRead.model_validate(book)
