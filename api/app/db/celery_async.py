"""Isolated async DB access for Celery workers.

Celery prefork workers call asyncio.run() from sync task bodies. Reusing the
API's module-level async engine/session factory causes:
  RuntimeError: ... Future attached to a different loop

Each Celery DB operation gets a disposable engine disposed before the loop closes.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings

T = TypeVar("T")


async def _with_disposable_session(
    fn: Callable[[AsyncSession], Awaitable[T]],
) -> T:
    settings = get_settings()
    engine: AsyncEngine = create_async_engine(settings.DB_URL, pool_pre_ping=True)
    factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    try:
        async with factory() as session:
            return await fn(session)
    finally:
        await engine.dispose()


def run_db(coro_builder: Callable[[AsyncSession], Awaitable[T]]) -> T:
    """Run an async DB coroutine from a sync Celery task."""
    return asyncio.run(_with_disposable_session(coro_builder))
