"""Unit tests for school library upload service — T-055."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import ValidationError
from app.features.files.models import UploadRecord
from app.features.files.schemas import UploadInitiated, UploadStatus
from app.features.library.school_library_schemas import SchoolLibraryUploadRequest
from app.features.library.school_library_service import SchoolLibraryService
from app.features.library.school_models import (
    LibraryContentType,
    LibraryIngestionStatus,
    LibraryVisibility,
    SchoolLibraryItem,
    SchoolLibraryItemSelection,
)
from app.features.users.models import User, UserAccountStatus, UserRole


def _teacher(user_id: str = "teacher-1", school_id: str = "school-1") -> User:
    return User(
        id=user_id,
        authentik_id="auth-teacher-1",
        email="teacher@test.com",
        display_name="Teacher",
        role=UserRole.TEACHER,
        status=UserAccountStatus.ACTIVE,
        school_id=school_id,
    )


def _item(**kwargs: object) -> SchoolLibraryItem:
    base = SchoolLibraryItem(
        id="item-1",
        school_id="school-1",
        title="Physics Notes",
        content_type=LibraryContentType.REFERENCE,
        language="en",
        subject_id=None,
        grade_level_ordinal=None,
        storage_key="school-library/school-1/file.pdf",
        sha256="a" * 64,
        ingestion_status=LibraryIngestionStatus.PENDING,
        created_by="teacher-1",
        visibility=LibraryVisibility.PRIVATE,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    for key, value in kwargs.items():
        setattr(base, key, value)
    return base


@pytest.mark.asyncio
async def test_upload_creates_pending_item() -> None:
    session = AsyncMock()
    svc = SchoolLibraryService(session)
    teacher = _teacher()
    meta = SchoolLibraryUploadRequest(title="Physics Notes")
    upload_result = UploadInitiated(
        upload_id="upload-1",
        status=UploadStatus.READY,
        status_url="/api/v1/uploads/upload-1",
    )
    upload_record = UploadRecord(
        id="upload-1",
        profile="school_library_content",
        filename="notes.pdf",
        size_bytes=100,
        sha256="b" * 64,
        minio_key="school-library/school-1/notes.pdf",
        bucket="pdfs",
        school_id="school-1",
        uploaded_by="teacher-1",
        status=UploadStatus.READY,
    )
    saved_item = _item(id="item-new", sha256="b" * 64)

    with (
        patch.object(svc._users, "get_by_authentik_id", return_value=teacher),
        patch.object(svc._repo, "get_by_school_sha256", return_value=None),
        patch(
            "app.features.library.school_library_service.run_upload_pipeline",
            return_value=upload_result,
        ),
        patch.object(session, "get", return_value=upload_record),
        patch.object(svc._repo, "save_item", return_value=saved_item),
        patch.object(svc._repo, "get_selection", return_value=None),
        patch.object(
            svc._repo,
            "save_selection",
            return_value=SchoolLibraryItemSelection(
                id="sel-1", library_item_id="item-new", user_id="teacher-1"
            ),
        ),
        patch("app.features.library.school_library_service.sha256_of_bytes", return_value="b" * 64),
        patch(
            "app.features.library.school_tasks.ingest_school_library_item.apply_async"
        ) as mock_ingest,
    ):
        result = await svc.upload(
            data=b"%PDF-1.4 test",
            filename="notes.pdf",
            meta=meta,
            authentik_id="auth-teacher-1",
        )

    assert result.item.ingestion_status == "pending"
    assert result.storage_deduplicated is False
    assert result.selection_created is True
    mock_ingest.assert_called_once_with(
        args=["item-new", "school-1"],
        queue="ingestion",
    )


@pytest.mark.asyncio
async def test_upload_dedup_requeues_ingestion_when_pending() -> None:
    session = AsyncMock()
    svc = SchoolLibraryService(session)
    teacher2 = _teacher(user_id="teacher-2")
    existing = _item(created_by="teacher-1", ingestion_status=LibraryIngestionStatus.PENDING)
    meta = SchoolLibraryUploadRequest(title="Physics Notes")

    with (
        patch.object(svc._users, "get_by_authentik_id", return_value=teacher2),
        patch.object(svc._repo, "get_by_school_sha256", return_value=existing),
        patch.object(svc._repo, "get_selection", return_value=None),
        patch.object(
            svc._repo,
            "save_selection",
            return_value=SchoolLibraryItemSelection(
                id="sel-2", library_item_id="item-1", user_id="teacher-2"
            ),
        ),
        patch("app.features.library.school_library_service.sha256_of_bytes", return_value="a" * 64),
        patch(
            "app.features.library.school_tasks.ingest_school_library_item.apply_async"
        ) as mock_ingest,
    ):
        await svc.upload(
            data=b"%PDF-same",
            filename="notes.pdf",
            meta=meta,
            authentik_id="auth-teacher-1",
        )

    mock_ingest.assert_called_once_with(args=["item-1", "school-1"], queue="ingestion")


@pytest.mark.asyncio
async def test_upload_dedup_reuses_existing_item_and_creates_selection() -> None:
    session = AsyncMock()
    svc = SchoolLibraryService(session)
    teacher2 = _teacher(user_id="teacher-2")
    existing = _item(
        created_by="teacher-1",
        ingestion_status=LibraryIngestionStatus.AVAILABLE,
    )
    meta = SchoolLibraryUploadRequest(title="Physics Notes")

    with (
        patch.object(svc._users, "get_by_authentik_id", return_value=teacher2),
        patch.object(svc._repo, "get_by_school_sha256", return_value=existing),
        patch.object(svc._repo, "get_selection", return_value=None),
        patch.object(
            svc._repo,
            "save_selection",
            return_value=SchoolLibraryItemSelection(
                id="sel-2", library_item_id="item-1", user_id="teacher-2"
            ),
        ),
        patch("app.features.library.school_library_service.sha256_of_bytes", return_value="a" * 64),
        patch(
            "app.features.library.school_tasks.ingest_school_library_item.apply_async"
        ) as mock_ingest,
    ):
        result = await svc.upload(
            data=b"%PDF-same",
            filename="notes.pdf",
            meta=meta,
            authentik_id="auth-teacher-1",
        )

    assert result.storage_deduplicated is True
    assert result.item.id == "item-1"
    assert result.selection_created is True
    mock_ingest.assert_not_called()


@pytest.mark.asyncio
async def test_upload_rejects_invalid_pdf() -> None:
    session = AsyncMock()
    svc = SchoolLibraryService(session)
    teacher = _teacher()
    meta = SchoolLibraryUploadRequest(title="Bad file")

    with (
        patch.object(svc._users, "get_by_authentik_id", return_value=teacher),
        patch.object(svc._repo, "get_by_school_sha256", return_value=None),
        patch(
            "app.features.library.school_library_service.run_upload_pipeline",
            side_effect=ValueError("File does not match expected format"),
        ),
        patch("app.features.library.school_library_service.sha256_of_bytes", return_value="c" * 64),
    ):
        with pytest.raises(ValidationError):
            await svc.upload(
                data=b"not-a-pdf",
                filename="bad.txt",
                meta=meta,
                authentik_id="auth-teacher-1",
            )


@pytest.mark.asyncio
async def test_curriculum_forces_school_public_visibility() -> None:
    session = AsyncMock()
    svc = SchoolLibraryService(session)
    teacher = _teacher()
    meta = SchoolLibraryUploadRequest(
        title="Punjab Physics", content_type="curriculum", visibility="private"
    )
    upload_result = UploadInitiated(
        upload_id="upload-1",
        status=UploadStatus.READY,
        status_url="/api/v1/uploads/upload-1",
    )
    upload_record = UploadRecord(
        id="upload-1",
        profile="school_library_content",
        filename="curriculum.pdf",
        size_bytes=100,
        sha256="d" * 64,
        minio_key="school-library/school-1/curriculum.pdf",
        bucket="pdfs",
        school_id="school-1",
        uploaded_by="teacher-1",
        status=UploadStatus.READY,
    )
    saved_item = _item(
        id="item-curriculum",
        sha256="d" * 64,
        content_type=LibraryContentType.CURRICULUM,
        visibility=LibraryVisibility.SCHOOL_PUBLIC,
    )

    with (
        patch.object(svc._users, "get_by_authentik_id", return_value=teacher),
        patch.object(svc._repo, "get_by_school_sha256", return_value=None),
        patch(
            "app.features.library.school_library_service.run_upload_pipeline",
            return_value=upload_result,
        ),
        patch.object(session, "get", return_value=upload_record),
        patch.object(svc._repo, "save_item", return_value=saved_item) as save_item,
        patch.object(svc._repo, "get_selection", return_value=None),
        patch.object(
            svc._repo,
            "save_selection",
            return_value=SchoolLibraryItemSelection(
                id="sel-1", library_item_id="item-curriculum", user_id="teacher-1"
            ),
        ),
        patch("app.features.library.school_library_service.sha256_of_bytes", return_value="d" * 64),
        patch("app.features.library.school_tasks.ingest_school_library_item.apply_async"),
    ):
        await svc.upload(
            data=b"%PDF-curriculum",
            filename="curriculum.pdf",
            meta=meta,
            authentik_id="auth-teacher-1",
        )

    created = save_item.await_args.args[0]
    assert created.visibility is LibraryVisibility.SCHOOL_PUBLIC


@pytest.mark.asyncio
async def test_get_item_returns_curriculum_for_school_member() -> None:
    session = AsyncMock()
    svc = SchoolLibraryService(session)
    teacher = _teacher()
    item = _item(
        content_type=LibraryContentType.CURRICULUM,
        visibility=LibraryVisibility.SCHOOL_PUBLIC,
        topic_tree_jsonb={"chapters": [], "parse_degraded": False},
    )

    with (
        patch.object(svc._users, "get_by_authentik_id", return_value=teacher),
        patch.object(svc._repo, "get_by_id", return_value=item),
    ):
        result = await svc.get_item("item-1", authentik_id="auth-teacher-1")

    assert result.content_type is LibraryContentType.CURRICULUM
    assert result.topic_tree_jsonb is not None


@pytest.mark.asyncio
async def test_get_item_hides_other_teachers_private_reference() -> None:
    from app.core.exceptions import NotFoundError

    session = AsyncMock()
    svc = SchoolLibraryService(session)
    viewer = _teacher(user_id="teacher-2")
    private_item = _item(created_by="teacher-1", visibility=LibraryVisibility.PRIVATE)

    with (
        patch.object(svc._users, "get_by_authentik_id", return_value=viewer),
        patch.object(svc._repo, "get_by_id", return_value=private_item),
        patch.object(svc._repo, "get_selection", return_value=None),
    ):
        with pytest.raises(NotFoundError):
            await svc.get_item("item-1", authentik_id="auth-teacher-1")


@pytest.mark.asyncio
async def test_publish_reference_makes_private_item_public() -> None:
    session = AsyncMock()
    svc = SchoolLibraryService(session)
    teacher = _teacher()
    private_item = _item(visibility=LibraryVisibility.PRIVATE)

    with (
        patch.object(svc._users, "get_by_authentik_id", return_value=teacher),
        patch.object(svc._repo, "get_by_id", return_value=private_item),
        patch.object(svc._repo, "update_item", return_value=private_item) as update_item,
        patch(
            "app.features.library.school_library_notifications.notify_library_item_published",
            new_callable=AsyncMock,
        ),
    ):
        result = await svc.publish_reference("item-1", authentik_id="auth-teacher-1")

    assert result.visibility is LibraryVisibility.SCHOOL_PUBLIC
    update_item.assert_awaited_once()


@pytest.mark.asyncio
async def test_publish_reference_idempotent_when_already_public() -> None:
    session = AsyncMock()
    svc = SchoolLibraryService(session)
    teacher = _teacher()
    public_item = _item(visibility=LibraryVisibility.SCHOOL_PUBLIC)

    with (
        patch.object(svc._users, "get_by_authentik_id", return_value=teacher),
        patch.object(svc._repo, "get_by_id", return_value=public_item),
        patch.object(svc._repo, "update_item") as update_item,
    ):
        result = await svc.publish_reference("item-1", authentik_id="auth-teacher-1")

    assert result.visibility is LibraryVisibility.SCHOOL_PUBLIC
    update_item.assert_not_called()


@pytest.mark.asyncio
async def test_set_reference_visibility_blocks_unpublish() -> None:
    from app.core.exceptions import PreconditionFailedError

    session = AsyncMock()
    svc = SchoolLibraryService(session)
    teacher = _teacher()
    public_item = _item(visibility=LibraryVisibility.SCHOOL_PUBLIC)

    with (
        patch.object(svc._users, "get_by_authentik_id", return_value=teacher),
        patch.object(svc._repo, "get_by_id", return_value=public_item),
    ):
        with pytest.raises(PreconditionFailedError, match="cannot be made private"):
            await svc.set_reference_visibility(
                "item-1", visibility="private", authentik_id="auth-teacher-1"
            )


@pytest.mark.asyncio
async def test_remove_selection_soft_deletes_selection() -> None:
    session = AsyncMock()
    svc = SchoolLibraryService(session)
    teacher = _teacher()
    public_item = _item(visibility=LibraryVisibility.SCHOOL_PUBLIC)
    selection = SchoolLibraryItemSelection(
        id="sel-1", library_item_id="item-1", user_id="teacher-1"
    )

    with (
        patch.object(svc._users, "get_by_authentik_id", return_value=teacher),
        patch.object(svc._repo, "get_by_id", return_value=public_item),
        patch.object(svc._repo, "get_selection", return_value=selection),
        patch.object(svc._repo, "soft_delete_selection") as soft_delete,
    ):
        result = await svc.remove_selection("item-1", authentik_id="auth-teacher-1")

    assert result.id == "item-1"
    soft_delete.assert_awaited_once_with(selection)


@pytest.mark.asyncio
async def test_soft_delete_item_sets_deleted_at_and_audits() -> None:
    session = AsyncMock()
    svc = SchoolLibraryService(session)
    teacher = _teacher()
    curriculum = _item(
        content_type=LibraryContentType.CURRICULUM,
        visibility=LibraryVisibility.SCHOOL_PUBLIC,
        created_by="teacher-1",
    )
    deleted = _item(
        content_type=LibraryContentType.CURRICULUM,
        visibility=LibraryVisibility.SCHOOL_PUBLIC,
        created_by="teacher-1",
    )
    deleted.deleted_at = datetime.now(timezone.utc)

    async def _fake_audit(**kwargs: object) -> None:
        pass

    with (
        patch.object(svc._users, "get_by_authentik_id", return_value=teacher),
        patch.object(svc._repo, "get_by_id", return_value=curriculum),
        patch.object(svc._repo, "soft_delete_item", return_value=deleted) as soft_delete,
        patch("app.features.library.school_library_service.audit", _fake_audit),
    ):
        result = await svc.soft_delete_item("item-1", authentik_id="auth-teacher-1")

    assert result.deleted_at is not None
    soft_delete.assert_awaited_once_with(curriculum)


@pytest.mark.asyncio
async def test_soft_delete_item_blocks_non_owner_teacher() -> None:
    from app.core.exceptions import PermissionDeniedError

    session = AsyncMock()
    svc = SchoolLibraryService(session)
    teacher = _teacher()
    other_item = _item(created_by="other-teacher")

    with (
        patch.object(svc._users, "get_by_authentik_id", return_value=teacher),
        patch.object(svc._repo, "get_by_id", return_value=other_item),
    ):
        with pytest.raises(PermissionDeniedError):
            await svc.soft_delete_item("item-1", authentik_id="auth-teacher-1")


@pytest.mark.asyncio
async def test_coordinator_reference_upload_forces_public() -> None:
    session = AsyncMock()
    svc = SchoolLibraryService(session)
    coordinator = _teacher(user_id="coord-1")
    coordinator.role = UserRole.COORDINATOR
    meta = SchoolLibraryUploadRequest(title="Shared Notes", visibility="private")
    upload_result = UploadInitiated(
        upload_id="upload-1",
        status=UploadStatus.READY,
        status_url="/api/v1/uploads/upload-1",
    )
    upload_record = UploadRecord(
        id="upload-1",
        profile="school_library_content",
        filename="notes.pdf",
        size_bytes=100,
        sha256="e" * 64,
        minio_key="school-library/school-1/notes.pdf",
        bucket="pdfs",
        school_id="school-1",
        uploaded_by="coord-1",
        status=UploadStatus.READY,
    )
    saved_item = _item(id="item-coord", sha256="e" * 64, visibility=LibraryVisibility.SCHOOL_PUBLIC)

    with (
        patch.object(svc._users, "get_by_authentik_id", return_value=coordinator),
        patch.object(svc._repo, "get_by_school_sha256", return_value=None),
        patch(
            "app.features.library.school_library_service.run_upload_pipeline",
            return_value=upload_result,
        ),
        patch.object(session, "get", return_value=upload_record),
        patch.object(svc._repo, "save_item", return_value=saved_item) as save_item,
        patch.object(svc._repo, "get_selection", return_value=None),
        patch.object(
            svc._repo,
            "save_selection",
            return_value=SchoolLibraryItemSelection(
                id="sel-1", library_item_id="item-coord", user_id="coord-1"
            ),
        ),
        patch("app.features.library.school_library_service.sha256_of_bytes", return_value="e" * 64),
        patch("app.features.library.school_tasks.ingest_school_library_item.apply_async"),
    ):
        await svc.upload(
            data=b"%PDF-reference",
            filename="notes.pdf",
            meta=meta,
            authentik_id="auth-teacher-1",
        )

    created = save_item.await_args.args[0]
    assert created.visibility is LibraryVisibility.SCHOOL_PUBLIC


@pytest.mark.asyncio
async def test_retry_ingestion_resets_failed_item_to_pending() -> None:
    session = AsyncMock()
    svc = SchoolLibraryService(session)
    teacher = _teacher()
    failed_item = _item(
        ingestion_status=LibraryIngestionStatus.FAILED,
        ingestion_error="MinIO down",
    )

    with (
        patch.object(svc._users, "get_by_authentik_id", return_value=teacher),
        patch.object(svc._repo, "get_by_id", return_value=failed_item),
        patch.object(svc._repo, "update_item", return_value=failed_item) as update_item,
        patch(
            "app.features.library.school_tasks.ingest_school_library_item.apply_async"
        ) as mock_ingest,
    ):
        result = await svc.retry_ingestion("item-1", authentik_id="auth-teacher-1")

    assert result.ingestion_status is LibraryIngestionStatus.PENDING
    assert result.ingestion_error is None
    update_item.assert_awaited_once()
    mock_ingest.assert_called_once_with(args=["item-1", "school-1"], queue="ingestion")


@pytest.mark.asyncio
async def test_list_items_delegates_to_repository() -> None:
    session = AsyncMock()
    svc = SchoolLibraryService(session)
    teacher = _teacher()
    public_item = _item(visibility=LibraryVisibility.SCHOOL_PUBLIC)

    with (
        patch.object(svc._users, "get_by_authentik_id", return_value=teacher),
        patch.object(
            svc._repo,
            "list_for_user",
            return_value=([public_item], 1),
        ) as list_for_user,
    ):
        result = await svc.list_items(
            authentik_id="auth-teacher-1",
            subject_id="subj-1",
            title="Physics",
        )

    assert result.total == 1
    assert result.items[0].visibility == "school_public"
    list_for_user.assert_awaited_once_with(
        school_id="school-1",
        user_id="teacher-1",
        subject_id="subj-1",
        grade_level_ordinal=None,
        language=None,
        content_type=None,
        title="Physics",
        limit=50,
        offset=0,
    )
