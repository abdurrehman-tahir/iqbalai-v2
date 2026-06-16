"""School Content Library upload service — T-055."""

from __future__ import annotations

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from app.features.files.models import UploadRecord
from app.features.files.pipeline import run_upload_pipeline
from app.features.files.profiles import get_profile
from app.features.files.schemas import UploadStatus
from app.features.library.school_library_repository import SchoolLibraryRepository
from app.features.library.school_library_schemas import (
    SchoolLibraryItemRead,
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

    def _resolve_visibility(self, meta: SchoolLibraryUploadRequest) -> LibraryVisibility:
        if meta.content_type == LibraryContentType.CURRICULUM.value:
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
        visibility = self._resolve_visibility(meta)

        existing_item = await self._repo.get_by_school_sha256(user.school_id, file_sha256)
        if existing_item is not None:
            _, selection_created = await self._ensure_selection(existing_item.id, user.id)
            if existing_item.ingestion_status in (
                LibraryIngestionStatus.PENDING,
                LibraryIngestionStatus.FAILED,
            ):
                self._enqueue_ingestion(existing_item)
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

    async def get_item(self, item_id: str, authentik_id: str) -> SchoolLibraryItem:
        """Return a library item visible to the caller."""
        user = await self._require_uploader(authentik_id)
        assert user.school_id is not None
        item = await self._repo.get_by_id(item_id)
        if item is None or item.school_id != user.school_id:
            raise NotFoundError("Library item not found")
        if not await self._can_view_item(item, user.id):
            raise NotFoundError("Library item not found")
        return item

    async def _can_view_item(self, item: SchoolLibraryItem, user_id: str) -> bool:
        if item.visibility is LibraryVisibility.SCHOOL_PUBLIC:
            return True
        if item.created_by == user_id:
            return True
        selection = await self._repo.get_selection(item.id, user_id)
        return selection is not None
