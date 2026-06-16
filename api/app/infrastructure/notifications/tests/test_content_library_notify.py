"""Content library notification dispatcher tests — T-065."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.infrastructure.notifications.content_library import notify_content_library_event


@pytest.mark.asyncio
async def test_notify_content_library_event_in_app() -> None:
    session = AsyncMock()
    with patch(
        "app.infrastructure.notifications.content_library.publish_notification",
        new_callable=AsyncMock,
    ) as publish:
        await notify_content_library_event(
            session=session,
            template_key="content_library.item_available",
            recipient_user_id="teacher-1",
            school_id="school-1",
            params={"title": "Notes", "content_type": "reference"},
        )

    publish.assert_awaited_once()
    assert publish.await_args.kwargs["feature_namespace"] == "content_library"
    assert publish.await_args.kwargs["template_key"] == "content_library.item_available"
