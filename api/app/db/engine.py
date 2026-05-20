"""SQLAlchemy async engine."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.config import get_settings

_engine: AsyncEngine | None = None


def get_engine() -> AsyncEngine:
    """Return the singleton async engine, creating it on first call."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.DB_URL,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            echo=False,
        )
    return _engine
