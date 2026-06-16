"""School Content Library repository — T-055."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import not_deleted
from app.features.library.school_models import SchoolLibraryItem, SchoolLibraryItemSelection


class SchoolLibraryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_school_sha256(self, school_id: str, sha256: str) -> SchoolLibraryItem | None:
        result = await self._session.execute(
            select(SchoolLibraryItem).where(
                SchoolLibraryItem.school_id == school_id,
                SchoolLibraryItem.sha256 == sha256,
                not_deleted(SchoolLibraryItem),
            )
        )
        return result.scalar_one_or_none()

    async def get_selection(
        self, library_item_id: str, user_id: str
    ) -> SchoolLibraryItemSelection | None:
        result = await self._session.execute(
            select(SchoolLibraryItemSelection).where(
                SchoolLibraryItemSelection.library_item_id == library_item_id,
                SchoolLibraryItemSelection.user_id == user_id,
                not_deleted(SchoolLibraryItemSelection),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, item_id: str) -> SchoolLibraryItem | None:
        result = await self._session.execute(
            select(SchoolLibraryItem).where(
                SchoolLibraryItem.id == item_id,
                not_deleted(SchoolLibraryItem),
            )
        )
        return result.scalar_one_or_none()

    async def save_item(self, item: SchoolLibraryItem) -> SchoolLibraryItem:
        self._session.add(item)
        await self._session.commit()
        await self._session.refresh(item)
        return item

    async def save_selection(
        self, selection: SchoolLibraryItemSelection
    ) -> SchoolLibraryItemSelection:
        self._session.add(selection)
        await self._session.commit()
        await self._session.refresh(selection)
        return selection

    async def update_item(self, item: SchoolLibraryItem) -> SchoolLibraryItem:
        await self._session.commit()
        await self._session.refresh(item)
        return item

    async def soft_delete_selection(self, selection: SchoolLibraryItemSelection) -> None:
        selection.deleted_at = datetime.now(timezone.utc)
        await self._session.commit()
