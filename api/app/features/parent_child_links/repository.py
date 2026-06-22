"""ParentChildLink repository — T-081."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import not_deleted
from app.features.parent_child_links.models import ParentChildLink, ParentChildLinkStatus


class ParentChildLinkRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, link_id: str) -> ParentChildLink | None:
        result = await self._session.execute(
            select(ParentChildLink).where(
                ParentChildLink.id == link_id,
                not_deleted(ParentChildLink),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_parent_and_student(
        self, *, parent_user_id: str, student_user_id: str
    ) -> ParentChildLink | None:
        result = await self._session.execute(
            select(ParentChildLink).where(
                ParentChildLink.parent_user_id == parent_user_id,
                ParentChildLink.student_user_id == student_user_id,
                not_deleted(ParentChildLink),
            )
        )
        return result.scalar_one_or_none()

    async def list_for_parent(self, parent_user_id: str) -> list[ParentChildLink]:
        result = await self._session.execute(
            select(ParentChildLink)
            .where(
                ParentChildLink.parent_user_id == parent_user_id,
                not_deleted(ParentChildLink),
            )
            .order_by(ParentChildLink.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_pending_for_student(self, student_user_id: str) -> list[ParentChildLink]:
        result = await self._session.execute(
            select(ParentChildLink)
            .where(
                ParentChildLink.student_user_id == student_user_id,
                ParentChildLink.status == ParentChildLinkStatus.PENDING,
                not_deleted(ParentChildLink),
            )
            .order_by(ParentChildLink.created_at.asc())
        )
        return list(result.scalars().all())

    async def list_approved_for_parent(self, parent_user_id: str) -> list[ParentChildLink]:
        result = await self._session.execute(
            select(ParentChildLink)
            .where(
                ParentChildLink.parent_user_id == parent_user_id,
                ParentChildLink.status == ParentChildLinkStatus.APPROVED,
                not_deleted(ParentChildLink),
            )
            .order_by(ParentChildLink.approved_at.desc())
        )
        return list(result.scalars().all())

    async def create(self, link: ParentChildLink) -> ParentChildLink:
        self._session.add(link)
        await self._session.commit()
        await self._session.refresh(link)
        return link

    async def update(self, link: ParentChildLink) -> ParentChildLink:
        await self._session.commit()
        await self._session.refresh(link)
        return link
