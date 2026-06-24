"""M-04 milestone E2E demo flow — T-067 (harness + fixture PDF)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.features.audit.actions import (
    CAPACITY_OVERRIDE,
    CAPACITY_UPDATED,
    SCHOOL_LIBRARY_ITEM_INGESTED,
    SCHOOL_LIBRARY_ITEM_PUBLISHED,
    SCHOOL_LIBRARY_ITEM_UPLOADED,
)
from app.features.grades.cross_grade import library_item_visible_for_grade_context
from app.features.library.school_models import (
    LibraryContentType,
    LibraryIngestionStatus,
    LibraryVisibility,
)
from app.features.library.tests.test_school_library_service import _item, _teacher
from app.features.teacher_onboarding.schemas import TeacherCapacityUpdate, TeacherOnboardingState
from app.features.teacher_onboarding.service import TeacherOnboardingService, derive_onboarding_state
from app.features.users.models import UserAccountStatus

FIXTURE_PDF = Path(__file__).resolve().parent / "fixtures" / "sample.pdf"


def test_fixture_pdf_exists_and_is_valid_header() -> None:
    assert FIXTURE_PDF.is_file()
    header = FIXTURE_PDF.read_bytes()[:8]
    assert header.startswith(b"%PDF-")


def test_onboarding_ready_derivation_after_assignment() -> None:
    from app.features.teacher_onboarding.models import TeacherProfile

    profile = TeacherProfile(
        user_id="teacher-1",
        name="Ali Khan",
        region_province="Punjab",
        region_district=None,
        bio=None,
        language_preference="en",
        subject_ids=["subj-1"],
        profile_completed_at=datetime.now(timezone.utc),
    )
    before = derive_onboarding_state(
        profile=profile,
        assignment_count=0,
        account_status=UserAccountStatus.ACTIVE,
        teacher_capacity=5,
    )
    after = derive_onboarding_state(
        profile=profile,
        assignment_count=1,
        account_status=UserAccountStatus.ACTIVE,
        teacher_capacity=5,
    )
    assert before.state is TeacherOnboardingState.PROFILE_COMPLETE
    assert before.ready_to_teach is False
    assert after.state is TeacherOnboardingState.READY_TO_TEACH
    assert after.ready_to_teach is True
    assert after.can_create_content is True


def test_cross_grade_library_visibility_matrix() -> None:
    """Grade 9 context sees grade 9 + 8; not grade 10; untagged always visible."""
    assert library_item_visible_for_grade_context(context_ordinal=9, item_grade_ordinal=9)
    assert library_item_visible_for_grade_context(context_ordinal=9, item_grade_ordinal=8)
    assert not library_item_visible_for_grade_context(context_ordinal=9, item_grade_ordinal=10)
    assert library_item_visible_for_grade_context(context_ordinal=9, item_grade_ordinal=None)
    assert library_item_visible_for_grade_context(context_ordinal=10, item_grade_ordinal=9)


@pytest.mark.asyncio
async def test_m04_library_publish_and_capacity_audit_flow() -> None:
    from app.features.library.school_library_service import SchoolLibraryService

    audit_actions: list[str] = []
    notifications: list[str] = []

    async def _audit(**kwargs: object) -> None:
        audit_actions.append(str(kwargs.get("action")))

    async def _notify(**kwargs: object) -> None:
        notifications.append(str(kwargs.get("template_key")))

    session = AsyncMock()
    library_svc = SchoolLibraryService(session)
    teacher = _teacher()
    private_ref = _item(
        content_type=LibraryContentType.REFERENCE,
        visibility=LibraryVisibility.PRIVATE,
        ingestion_status=LibraryIngestionStatus.AVAILABLE,
    )
    published_ref = _item(
        content_type=LibraryContentType.REFERENCE,
        visibility=LibraryVisibility.SCHOOL_PUBLIC,
        ingestion_status=LibraryIngestionStatus.AVAILABLE,
    )

    with (
        patch.object(library_svc._users, "get_by_authentik_id", AsyncMock(return_value=teacher)),
        patch.object(library_svc._repo, "get_by_id", AsyncMock(return_value=private_ref)),
        patch.object(library_svc._repo, "update_item", AsyncMock(return_value=published_ref)),
        patch("app.features.library.school_library_service.audit", _audit),
        patch(
            "app.features.library.school_library_notifications.notify_content_library_event",
            _notify,
        ),
        patch(
            "app.features.library.school_library_notifications.publish_content_library_mutation",
            AsyncMock(),
        ),
        patch(
            "app.features.library.school_library_notifications.list_teacher_ids_for_library_tags",
            AsyncMock(return_value=[]),
        ),
    ):
        result = await library_svc.publish_reference("item-1", authentik_id="auth-teacher-1")

    assert result.visibility is LibraryVisibility.SCHOOL_PUBLIC
    assert SCHOOL_LIBRARY_ITEM_PUBLISHED in audit_actions
    assert "content_library.item_published" in notifications

    teacher.teacher_capacity = 5
    onboarding_svc = TeacherOnboardingService(session)
    with (
        patch.object(onboarding_svc._user_repo, "get_by_authentik_id", AsyncMock(return_value=teacher)),
        patch.object(
            onboarding_svc._offering_repo,
            "count_active_assignments_for_teacher",
            AsyncMock(return_value=3),
        ),
        patch.object(onboarding_svc._user_repo, "update", AsyncMock(return_value=teacher)),
        patch.object(onboarding_svc._user_repo, "list_by_school_and_role", AsyncMock(return_value=[])),
        patch("app.features.teacher_onboarding.service.audit", _audit),
        patch("app.features.teacher_onboarding.service.notify_account_event", _notify),
    ):
        capacity_result = await onboarding_svc.update_capacity(
            TeacherCapacityUpdate(teacher_capacity=8),
            claims={"sub": "auth-teacher-1"},
        )

    assert capacity_result.teacher_capacity == 8
    assert capacity_result.assignment_count == 3
    assert capacity_result.capacity_below_assignments is False
    assert CAPACITY_UPDATED in audit_actions
    assert "account.capacity_changed" in notifications
    assert CAPACITY_OVERRIDE == "capacity.override"
    assert SCHOOL_LIBRARY_ITEM_UPLOADED == "school_library_item.uploaded"
    assert SCHOOL_LIBRARY_ITEM_INGESTED == "school_library_item.ingested"
