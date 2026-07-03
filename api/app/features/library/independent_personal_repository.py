"""Independent private pool repository — T-074."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import not_deleted
from app.features.library.independent_personal_models import IndependentPersonalContent


class IndependentPersonalContentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, content_id: str) -> IndependentPersonalContent | None:
        result = await self._session.execute(
            select(IndependentPersonalContent).where(IndependentPersonalContent.id == content_id)
        )
        return result.scalar_one_or_none()

    async def get_by_user_sha256(
        self, user_id: str, file_sha256: str
    ) -> IndependentPersonalContent | None:
        result = await self._session.execute(
            select(IndependentPersonalContent).where(
                IndependentPersonalContent.user_id == user_id,
                IndependentPersonalContent.file_sha256 == file_sha256,
                not_deleted(IndependentPersonalContent),
            )
        )
        return result.scalar_one_or_none()

    async def list_for_user(
        self,
        user_id: str,
        *,
        limit: int = 50,
        offset: int = 0,
        content_type: str | None = None,
        title: str | None = None,
    ) -> list[IndependentPersonalContent]:
        stmt = (
            select(IndependentPersonalContent)
            .where(
                IndependentPersonalContent.user_id == user_id,
                not_deleted(IndependentPersonalContent),
            )
            .order_by(IndependentPersonalContent.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if content_type is not None:
            stmt = stmt.where(IndependentPersonalContent.content_type == content_type)
        if title is not None:
            stmt = stmt.where(IndependentPersonalContent.title.ilike(f"%{title}%"))
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_for_user(
        self,
        user_id: str,
        *,
        content_type: str | None = None,
        title: str | None = None,
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(IndependentPersonalContent)
            .where(
                IndependentPersonalContent.user_id == user_id,
                not_deleted(IndependentPersonalContent),
            )
        )
        if content_type is not None:
            stmt = stmt.where(IndependentPersonalContent.content_type == content_type)
        if title is not None:
            stmt = stmt.where(IndependentPersonalContent.title.ilike(f"%{title}%"))
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def save(self, item: IndependentPersonalContent) -> IndependentPersonalContent:
        self._session.add(item)
        await self._session.commit()
        await self._session.refresh(item)
        return item
