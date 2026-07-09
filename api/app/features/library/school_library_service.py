"""School Content Library upload service — T-055."""

from __future__ import annotations

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    NotFoundError,
    PermissionDeniedError,
    PreconditionFailedError,
    ValidationError,
)
from app.features.audit.actions import (
    SCHOOL_LIBRARY_ITEM_DELETED,
    SCHOOL_LIBRARY_ITEM_PUBLISHED,
    SCHOOL_LIBRARY_ITEM_SELECTION_REMOVED,
    SCHOOL_LIBRARY_ITEM_UPLOADED,
)
from app.features.files.models import UploadRecord
from app.features.files.pipeline import run_upload_pipeline
from app.features.files.profiles import get_profile
from app.features.files.schemas import UploadStatus
from app.features.grades.cross_grade import assert_cross_grade_access_by_ordinal
from app.features.library.school_library_repository import SchoolLibraryRepository
from app.features.library.school_library_schemas import (
    SchoolLibraryItemRead,
    SchoolLibraryListResponse,
    SchoolLibraryUploadRequest,
    SchoolLibraryUploadResponse,
)
from app.features.library.school_models import (
    LibraryContentType,
    LibraryIngestionStatus,
    LibraryVisibility,
    SchoolLibraryItem,
    SchoolLibraryItemSelection,
)
from app.features.users.models import User, UserRole
from app.features.users.repository import UserRepository
from app.infrastructure.audit.log import audit
from app.infrastructure.storage.client import sha256_of_bytes

logger = structlog.get_logger(__name__)

_PROFILE_NAME = "school_library_content"
_UPLOAD_ROLES = {
    UserRole.TEACHER,
    UserRole.COORDINATOR,
    UserRole.SCHOOL_ADMIN,
    UserRole.DISTRICT_ADMIN,
    UserRole.PLATFORM_ADMIN,
}
_ADMIN_UPLOAD_ROLES = {
    UserRole.COORDINATOR,
    UserRole.SCHOOL_ADMIN,
    UserRole.DISTRICT_ADMIN,
    UserRole.PLATFORM_ADMIN,
}
_UNPUBLISH_BLOCKED_MESSAGE = (
    "Once shared with the school, content cannot be made private. "
    "You can remove your selection but the content stays available to others."
)


class SchoolLibraryService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = SchoolLibraryRepository(session)
        self._users = UserRepository(session)

    async def _require_uploader(self, authentik_id: str) -> User:
        user = await self._users.get_by_authentik_id(authentik_id)
        if user is None or user.deleted_at is not None:
            raise NotFoundError("User not found")
        if user.role not in _UPLOAD_ROLES:
            raise PermissionDeniedError("Only school staff can upload to the content library")
        if user.school_id is None:
            raise PermissionDeniedError("Uploader must belong to a school")
        return user

    def _resolve_visibility(
        self, meta: SchoolLibraryUploadRequest, user: User
    ) -> LibraryVisibility:
        if meta.content_type == LibraryContentType.CURRICULUM.value:
            return LibraryVisibility.SCHOOL_PUBLIC
        if user.role in _ADMIN_UPLOAD_ROLES:
            return LibraryVisibility.SCHOOL_PUBLIC
        return LibraryVisibility(meta.visibility)

    async def _get_upload_record(self, upload_id: str) -> UploadRecord:
        record = await self._session.get(UploadRecord, upload_id)
        if record is None or record.deleted_at is not None:
            raise NotFoundError("Upload record not found after pipeline")
        return record

    async def _ensure_selection(
        self, library_item_id: str, user_id: str
    ) -> tuple[SchoolLibraryItemSelection | None, bool]:
        existing = await self._repo.get_selection(library_item_id, user_id)
        if existing is not None:
            return existing, False
        selection = SchoolLibraryItemSelection(
            library_item_id=library_item_id,
            user_id=user_id,
        )
        created = await self._repo.save_selection(selection)
        return created, True

    async def upload(
        self,
        *,
        data: bytes,
        filename: str,
        meta: SchoolLibraryUploadRequest,
        authentik_id: str,
    ) -> SchoolLibraryUploadResponse:
        """Upload a PDF to the school library with per-school storage dedup."""
        user = await self._require_uploader(authentik_id)
        assert user.school_id is not None
        profile = get_profile(_PROFILE_NAME)
        file_sha256 = sha256_of_bytes(data)
        visibility = self._resolve_visibility(meta, user)

        existing_item = await self._repo.get_by_school_sha256(user.school_id, file_sha256)
        if existing_item is not None:
            _, selection_created = await self._ensure_selection(existing_item.id, user.id)
            if existing_item.ingestion_status in (
                LibraryIngestionStatus.PENDING,
                LibraryIngestionStatus.FAILED,
            ):
                self._enqueue_ingestion(existing_item)
            await audit(
                session=self._session,
                action=SCHOOL_LIBRARY_ITEM_UPLOADED,
                actor_id=authentik_id,
                actor_role=user.role.value,
                target_type="school_library_item",
                target_id=existing_item.id,
                school_id=user.school_id,
                metadata={
                    "title": existing_item.title,
                    "storage_deduplicated": True,
                    "selection_created": selection_created,
                },
            )
            logger.info(
                "school_library_upload_deduped",
                item_id=existing_item.id,
                school_id=user.school_id,
                sha256=file_sha256,
            )
            return SchoolLibraryUploadResponse(
                item=SchoolLibraryItemRead.model_validate(existing_item),
                storage_deduplicated=True,
                selection_created=selection_created,
                message=(
                    "Duplicate file in this school — storage reused; "
                    "linked via your library selection."
                ),
            )

        try:
            upload_result = await run_upload_pipeline(
                data=data,
                filename=filename,
                profile=profile,
                session=self._session,
                school_id=user.school_id,
                uploaded_by=user.id,
            )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        storage_deduplicated = upload_result.status is UploadStatus.DUPLICATE
        upload_record = await self._get_upload_record(upload_result.upload_id)

        item = SchoolLibraryItem(
            school_id=user.school_id,
            title=meta.title.strip(),
            content_type=LibraryContentType(meta.content_type),
            language=meta.language,
            subject_id=meta.subject_id,
            grade_level_ordinal=meta.grade_level_ordinal,
            storage_key=upload_record.minio_key,
            sha256=file_sha256,
            ingestion_status=LibraryIngestionStatus.PENDING,
            created_by=user.id,
            visibility=visibility,
        )
        saved = await self._repo.save_item(item)
        _, selection_created = await self._ensure_selection(saved.id, user.id)

        from app.features.library.school_library_notifications import publish_library_item_uploaded

        await publish_library_item_uploaded(self._session, saved, actor_id=user.id)

        await audit(
            session=self._session,
            action=SCHOOL_LIBRARY_ITEM_UPLOADED,
            actor_id=authentik_id,
            actor_role=user.role.value,
            target_type="school_library_item",
            target_id=saved.id,
            school_id=user.school_id,
            metadata={
                "title": saved.title,
                "content_type": saved.content_type.value,
                "storage_deduplicated": storage_deduplicated,
            },
        )

        self._enqueue_ingestion(saved)

        logger.info(
            "school_library_upload_created",
            item_id=saved.id,
            school_id=user.school_id,
            storage_deduplicated=storage_deduplicated,
        )
        return SchoolLibraryUploadResponse(
            item=SchoolLibraryItemRead.model_validate(saved),
            storage_deduplicated=storage_deduplicated,
            selection_created=selection_created,
            message="Upload accepted; item pending ingestion.",
        )

    def _enqueue_ingestion(self, item: SchoolLibraryItem) -> None:
        """Queue async RAG ingestion for a library item (T-056)."""
        from app.features.library.school_tasks import ingest_school_library_item

        ingest_school_library_item.apply_async(
            args=[item.id, item.school_id],
            queue="ingestion",
        )
        logger.info(
            "school_library_ingestion_queued",
            item_id=item.id,
            school_id=item.school_id,
        )

    async def get_item(
        self,
        item_id: str,
        authentik_id: str,
        *,
        grade_level_ordinal: int | None = None,
    ) -> SchoolLibraryItem:
        """Return a library item visible to the caller."""
        user = await self._require_uploader(authentik_id)
        assert user.school_id is not None
        item = await self._repo.get_by_id(item_id)
        if item is None or item.school_id != user.school_id:
            raise NotFoundError("Library item not found")
        if not await self._can_view_item(item, user.id):
            raise NotFoundError("Library item not found")
        if grade_level_ordinal is not None and item.grade_level_ordinal is not None:
            assert_cross_grade_access_by_ordinal(grade_level_ordinal, item.grade_level_ordinal)
        return item

    async def list_items(
        self,
        authentik_id: str,
        *,
        subject_id: str | None = None,
        grade_level_ordinal: int | None = None,
        language: str | None = None,
        content_type: str | None = None,
        title: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> SchoolLibraryListResponse:
        """List library items visible to the caller with optional tag/search filters."""
        user = await self._require_uploader(authentik_id)
        assert user.school_id is not None
        items, total = await self._repo.list_for_user(
            school_id=user.school_id,
            user_id=user.id,
            subject_id=subject_id,
            grade_level_ordinal=grade_level_ordinal,
            language=language,
            content_type=content_type,
            title=title,
            limit=limit,
            offset=offset,
        )
        return SchoolLibraryListResponse(
            items=[SchoolLibraryItemRead.model_validate(item) for item in items],
            total=total,
        )

    async def _can_view_item(self, item: SchoolLibraryItem, user_id: str) -> bool:
        if item.visibility is LibraryVisibility.SCHOOL_PUBLIC:
            return True
        if item.created_by == user_id:
            return True
        selection = await self._repo.get_selection(item.id, user_id)
        return selection is not None

    async def _get_school_item(self, item_id: str, school_id: str) -> SchoolLibraryItem:
        item = await self._repo.get_by_id(item_id)
        if item is None or item.school_id != school_id:
            raise NotFoundError("Library item not found")
        return item

    def _can_publish_reference(self, item: SchoolLibraryItem, user: User) -> bool:
        if item.content_type is not LibraryContentType.REFERENCE:
            return False
        if item.created_by == user.id:
            return True
        return user.role in _ADMIN_UPLOAD_ROLES

    def _can_delete_item(self, item: SchoolLibraryItem, user: User) -> bool:
        if item.created_by == user.id:
            return True
        return user.role in _ADMIN_UPLOAD_ROLES

    async def publish_reference(self, item_id: str, authentik_id: str) -> SchoolLibraryItem:
        """Publish a private reference book to the school library (one-way)."""
        user = await self._require_uploader(authentik_id)
        assert user.school_id is not None
        item = await self._get_school_item(item_id, user.school_id)
        if item.content_type is not LibraryContentType.REFERENCE:
            raise ValidationError("Only reference books can be published")
        if not self._can_publish_reference(item, user):
            raise PermissionDeniedError("You can only publish your own reference books")
        if item.visibility is LibraryVisibility.SCHOOL_PUBLIC:
            return item
        item.visibility = LibraryVisibility.SCHOOL_PUBLIC
        await self._repo.update_item(item)
        from app.features.library.school_library_notifications import notify_library_item_published

        await notify_library_item_published(self._session, item, actor=user)
        await audit(
            session=self._session,
            action=SCHOOL_LIBRARY_ITEM_PUBLISHED,
            actor_id=authentik_id,
            actor_role=user.role.value,
            target_type="school_library_item",
            target_id=item.id,
            school_id=user.school_id,
            metadata={"title": item.title},
        )
        logger.info(
            "school_library_reference_published",
            item_id=item.id,
            school_id=user.school_id,
            actor_id=user.id,
        )
        return item

    async def set_reference_visibility(
        self, item_id: str, visibility: str, authentik_id: str
    ) -> SchoolLibraryItem:
        """Set reference visibility; blocks public → private (flow-3 §3.4)."""
        target = LibraryVisibility(visibility)
        if target is LibraryVisibility.PRIVATE:
            user = await self._require_uploader(authentik_id)
            assert user.school_id is not None
            item = await self._get_school_item(item_id, user.school_id)
            if item.visibility is LibraryVisibility.SCHOOL_PUBLIC:
                raise PreconditionFailedError(_UNPUBLISH_BLOCKED_MESSAGE)
            raise ValidationError("Reference books are private by default at upload")
        return await self.publish_reference(item_id, authentik_id)

    async def remove_selection(self, item_id: str, authentik_id: str) -> SchoolLibraryItem:
        """Remove the caller's selection; public items stay available to others."""
        user = await self._require_uploader(authentik_id)
        assert user.school_id is not None
        item = await self._get_school_item(item_id, user.school_id)
        selection = await self._repo.get_selection(item_id, user.id)
        if selection is None:
            raise NotFoundError("Library selection not found")
        await self._repo.soft_delete_selection(selection)
        await audit(
            session=self._session,
            action=SCHOOL_LIBRARY_ITEM_SELECTION_REMOVED,
            actor_id=authentik_id,
            actor_role=user.role.value,
            target_type="school_library_item",
            target_id=item.id,
            school_id=user.school_id,
            metadata={"title": item.title, "visibility": item.visibility.value},
        )
        logger.info(
            "school_library_selection_removed",
            item_id=item.id,
            school_id=user.school_id,
            user_id=user.id,
        )
        return item

    async def soft_delete_item(self, item_id: str, authentik_id: str) -> SchoolLibraryItem:
        """Soft-delete a library item — row and vectors retained for citation integrity."""
        user = await self._require_uploader(authentik_id)
        assert user.school_id is not None
        item = await self._get_school_item(item_id, user.school_id)
        if not self._can_delete_item(item, user):
            raise PermissionDeniedError("You can only delete library items you uploaded")
        if not await self._can_view_item(item, user.id):
            raise NotFoundError("Library item not found")

        deleted = await self._repo.soft_delete_item(item)

        await audit(
            session=self._session,
            action=SCHOOL_LIBRARY_ITEM_DELETED,
            actor_id=authentik_id,
            actor_role=user.role.value,
            target_type="school_library_item",
            target_id=item.id,
            school_id=user.school_id,
            metadata={
                "title": item.title,
                "content_type": item.content_type.value,
                "visibility": item.visibility.value,
            },
        )

        from app.features.library.school_library_notifications import publish_library_item_deleted

        await publish_library_item_deleted(self._session, item, actor_id=user.id)

        logger.info(
            "school_library_item_soft_deleted",
            item_id=item.id,
            school_id=user.school_id,
            actor_id=user.id,
        )
        return deleted

    async def retry_ingestion(self, item_id: str, authentik_id: str) -> SchoolLibraryItem:
        """Re-queue ingestion for a failed or pending library item."""
        user = await self._require_uploader(authentik_id)
        assert user.school_id is not None
        item = await self._get_school_item(item_id, user.school_id)
        if not await self._can_view_item(item, user.id):
            raise NotFoundError("Library item not found")
        if item.ingestion_status is LibraryIngestionStatus.AVAILABLE:
            raise ValidationError("This item is already available")
        if item.ingestion_status is LibraryIngestionStatus.INGESTING:
            raise ValidationError("Ingestion is already in progress")
        item.ingestion_status = LibraryIngestionStatus.PENDING
        item.ingestion_error = None
        await self._repo.update_item(item)
        self._enqueue_ingestion(item)
        logger.info(
            "school_library_ingestion_retry_queued",
            item_id=item.id,
            school_id=user.school_id,
            actor_id=user.id,
        )
        return item
