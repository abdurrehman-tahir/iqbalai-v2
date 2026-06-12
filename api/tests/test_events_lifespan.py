"""EVENTS_ENABLED lifespan guard (T-236)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.infrastructure.events import close_nats, init_nats


@pytest.mark.asyncio
async def test_init_nats_skips_when_events_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EVENTS_ENABLED", "false")
    from app.config import get_settings

    get_settings.cache_clear()

    with patch("nats.connect", new_callable=AsyncMock) as mock_connect:
        await init_nats()
        mock_connect.assert_not_called()

    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_init_nats_connects_when_events_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EVENTS_ENABLED", "true")
    from app.config import get_settings

    get_settings.cache_clear()

    mock_nc = AsyncMock()
    with patch("nats.connect", new_callable=AsyncMock, return_value=mock_nc) as mock_connect:
        await init_nats()
        mock_connect.assert_awaited_once()
        await close_nats()
        mock_nc.close.assert_awaited_once()

    get_settings.cache_clear()
