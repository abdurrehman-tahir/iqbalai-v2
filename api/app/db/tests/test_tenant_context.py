"""Tests for Celery RLS helpers (tenant_context)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.db.tenant_context import apply_school_rls


@pytest.mark.asyncio
async def test_apply_school_rls_uses_set_config_not_set_local_keyword() -> None:
    """``SET LOCAL app.current_role`` is a Postgres syntax error; use set_config."""
    session = AsyncMock()
    session.execute = AsyncMock()

    await apply_school_rls(
        session,
        school_id="school-1",
        role="platform_admin",
        user_id="user-1",
    )

    assert session.execute.await_count == 3
    sql_texts = [str(c.args[0]) for c in session.execute.await_args_list]
    assert "set_config('app.current_role'" in sql_texts[0]
    assert "set_config('app.current_school_id'" in sql_texts[1]
    assert "set_config('app.current_user_id'" in sql_texts[2]
    assert all("SET LOCAL" not in sql for sql in sql_texts)
    assert session.execute.await_args_list[0].args[1] == {"role": "platform_admin"}
    assert session.execute.await_args_list[1].args[1] == {"school_id": "school-1"}
    assert session.execute.await_args_list[2].args[1] == {"user_id": "user-1"}
