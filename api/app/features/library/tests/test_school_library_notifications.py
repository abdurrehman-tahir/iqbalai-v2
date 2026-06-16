"""School library notification helper tests — T-065."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.features.library.school_library_notifications import (
    notify_library_item_published,
)
from app.features.library.school_models import LibraryContentType, LibraryVisibility
from app.features.library.tests.test_school_library_service import _item, _teacher


@pytest.mark.asyncio
async def test_publish_notifies_publisher_and_tagged_teachers() -> None:
    session = AsyncMock()
    actor = _teacher()
    item = _item(
        content_type=LibraryContentType.REFERENCE,
        visibility=LibraryVisibility.SCHOOL_PUBLIC,
        subject_id="subj-1",
        grade_level_ordinal=9,
        language="en",
    )

    with (
        patch(
            "app.features.library.school_library_notifications.notify_content_library_event",
            new_callable=AsyncMock,
        ) as notify,
        patch(
            "app.features.library.school_library_notifications.list_teacher_ids_for_library_tags",
            return_value=["teacher-2", "teacher-3"],
        ),
        patch(
            "app.features.library.school_library_notifications.publish_content_library_mutation",
            new_callable=AsyncMock,
        ) as publish_event,
    ):
        await notify_library_item_published(session, item, actor=actor)

    assert notify.await_count == 3
    publish_event.assert_awaited_once()
    publisher_call = notify.await_args_list[0].kwargs
    assert publisher_call["variant"] == "publisher"
    assert publisher_call["recipient_user_id"] == actor.id
