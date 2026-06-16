"""School Content Library repository — T-055."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import not_deleted
from app.features.library.school_models import (
    LibraryContentType,
    LibraryVisibility,
    SchoolLibraryItem,
    SchoolLibraryItemSelection,
)


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

    def _visible_to_user(self, school_id: str, user_id: str):
        selection_exists = (
            select(SchoolLibraryItemSelection.id)
            .where(
                SchoolLibraryItemSelection.library_item_id == SchoolLibraryItem.id,
                SchoolLibraryItemSelection.user_id == user_id,
                not_deleted(SchoolLibraryItemSelection),
            )
            .correlate(SchoolLibraryItem)
            .exists()
        )
        return or_(
            SchoolLibraryItem.visibility == LibraryVisibility.SCHOOL_PUBLIC,
            SchoolLibraryItem.created_by == user_id,
            selection_exists,
        )

    def _apply_list_filters(
        self,
        stmt,
        *,
        subject_id: str | None,
        grade_level_ordinal: int | None,
        language: str | None,
        content_type: str | None,
        title: str | None,
    ):
        if subject_id:
            stmt = stmt.where(SchoolLibraryItem.subject_id == subject_id)
        if grade_level_ordinal is not None:
            stmt = stmt.where(SchoolLibraryItem.grade_level_ordinal == grade_level_ordinal)
        if language:
            stmt = stmt.where(SchoolLibraryItem.language == language)
        if content_type:
            stmt = stmt.where(SchoolLibraryItem.content_type == LibraryContentType(content_type))
        if title:
            stmt = stmt.where(SchoolLibraryItem.title.ilike(f"%{title.strip()}%"))
        return stmt

    async def list_for_user(
        self,
        *,
        school_id: str,
        user_id: str,
        subject_id: str | None = None,
        grade_level_ordinal: int | None = None,
        language: str | None = None,
        content_type: str | None = None,
        title: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[SchoolLibraryItem], int]:
        base = select(SchoolLibraryItem).where(
            SchoolLibraryItem.school_id == school_id,
            not_deleted(SchoolLibraryItem),
            self._visible_to_user(school_id, user_id),
        )
        base = self._apply_list_filters(
            base,
            subject_id=subject_id,
            grade_level_ordinal=grade_level_ordinal,
            language=language,
            content_type=content_type,
            title=title,
        )

        count_stmt = select(func.count()).select_from(base.subquery())
        count_result = await self._session.execute(count_stmt)
        total = int(count_result.scalar_one())

        items_result = await self._session.execute(
            base.order_by(SchoolLibraryItem.created_at.desc()).limit(limit).offset(offset)
        )
        return list(items_result.scalars().all()), total
