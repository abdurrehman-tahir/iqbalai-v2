"""Cross-grade library visibility tests — T-063."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import PermissionDeniedError
from app.features.library.school_library_service import SchoolLibraryService
from app.features.library.school_models import LibraryContentType, LibraryVisibility
from app.features.library.tests.test_school_library_service import _item, _teacher


@pytest.mark.asyncio
async def test_get_item_blocks_higher_grade_in_context() -> None:
    session = AsyncMock()
    svc = SchoolLibraryService(session)
    teacher = _teacher()
    high_grade_item = _item(
        content_type=LibraryContentType.CURRICULUM,
        visibility=LibraryVisibility.SCHOOL_PUBLIC,
        grade_level_ordinal=10,
    )

    with (
        patch.object(svc._users, "get_by_authentik_id", return_value=teacher),
        patch.object(svc._repo, "get_by_id", return_value=high_grade_item),
    ):
        with pytest.raises(PermissionDeniedError):
            await svc.get_item(
                "item-1",
                authentik_id="auth-teacher-1",
                grade_level_ordinal=9,
            )


@pytest.mark.asyncio
async def test_get_item_allows_lower_grade_in_context() -> None:
    session = AsyncMock()
    svc = SchoolLibraryService(session)
    teacher = _teacher()
    lower_grade_item = _item(
        content_type=LibraryContentType.CURRICULUM,
        visibility=LibraryVisibility.SCHOOL_PUBLIC,
        grade_level_ordinal=8,
    )

    with (
        patch.object(svc._users, "get_by_authentik_id", return_value=teacher),
        patch.object(svc._repo, "get_by_id", return_value=lower_grade_item),
    ):
        result = await svc.get_item(
            "item-1",
            authentik_id="auth-teacher-1",
            grade_level_ordinal=9,
        )

    assert result.grade_level_ordinal == 8


@pytest.mark.asyncio
async def test_get_item_allows_untagged_reference_in_any_context() -> None:
    session = AsyncMock()
    svc = SchoolLibraryService(session)
    teacher = _teacher()
    untagged = _item(
        content_type=LibraryContentType.REFERENCE,
        visibility=LibraryVisibility.SCHOOL_PUBLIC,
        grade_level_ordinal=None,
    )

    with (
        patch.object(svc._users, "get_by_authentik_id", return_value=teacher),
        patch.object(svc._repo, "get_by_id", return_value=untagged),
    ):
        result = await svc.get_item(
            "item-1",
            authentik_id="auth-teacher-1",
            grade_level_ordinal=9,
        )

    assert result.grade_level_ordinal is None
