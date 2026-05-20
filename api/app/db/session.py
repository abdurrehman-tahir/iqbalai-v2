"""Async session factory."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.engine import get_engine


def _make_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=get_engine(),
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


async_session_factory = _make_session_factory()
