"""RLS context helpers for background jobs (ARCH §3.4, §10.4)."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def apply_school_rls(
    session: AsyncSession,
    *,
    school_id: str,
    role: str = "platform_admin",
    user_id: str | None = None,
) -> None:
    """Set transaction-scoped RLS variables for school-tier tables.

    Uses ``set_config(..., is_local=true)`` instead of ``SET LOCAL app.current_role``
    because ``current_role`` is a Postgres reserved keyword and
    ``SET LOCAL app.current_role = $1`` raises a syntax error under asyncpg.
    """
    await session.execute(
        text("SELECT set_config('app.current_role', :role, true)"),
        {"role": role},
    )
    await session.execute(
        text("SELECT set_config('app.current_school_id', :school_id, true)"),
        {"school_id": school_id},
    )
    if user_id is not None:
        await session.execute(
            text("SELECT set_config('app.current_user_id', :user_id, true)"),
            {"user_id": user_id},
        )
