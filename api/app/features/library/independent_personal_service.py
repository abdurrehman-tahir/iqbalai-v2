"""Independent private pool upload service — T-074."""

from __future__ import annotations

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from app.core.tenant import INDEPENDENT_ROLES
from app.features.files.models import UploadRecord
from app.features.files.pipeline import run_upload_pipeline
from app.features.files.profiles import get_profile
from app.features.files.schemas import UploadStatus
from app.features.independent_users.models import (
    IndependentUser,
    IndependentUserAccountStatus,
)
from app.features.independent_users.repository import IndependentUserRepository
from app.features.library.independent_personal_models import (
    IndependentPersonalContent,
    PersonalContentStatus,
    PersonalContentType,
    PersonalStructuredParsingStatus,
)
from app.features.library.independent_personal_repository import (
    IndependentPersonalContentRepository,
)
from app.features.library.independent_personal_schemas import (
    IndependentPersonalContentRead,
    IndependentPersonalListResponse,
    IndependentPersonalUploadRequest,
    IndependentPersonalUploadResponse,
)
from app.infrastructure.audit.log import audit
from app.infrastructure.rag.embedder import independent_personal_collection
from app.infrastructure.storage.client import sha256_of_bytes

logger = structlog.get_logger(__name__)

_PROFILE_NAME = "independent_personal_content"


class IndependentPersonalContentService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = IndependentPersonalContentRepository(session)
        self._users = IndependentUserRepository(session)

    async def _require_independent_user(self, authentik_id: str) -> IndependentUser:
        user = await self._users.get_by_authentik_id(authentik_id)
        if user is None or user.deleted_at is not None:
            raise NotFoundError("User not found")
        if user.role.value not in INDEPENDENT_ROLES:
            raise PermissionDeniedError("Only independent users can access the private pool")
        if user.status != IndependentUserAccountStatus.ACTIVE:
            raise PermissionDeniedError("Account is not active")
        return user

    async def _require_independent_user_from_claims(
        self, claims: dict[str, object]
    ) -> IndependentUser:
        role = str(claims.get("role", ""))
        if role not in INDEPENDENT_ROLES:
            raise PermissionDeniedError("Only independent users can access the private pool")
        return await self._require_independent_user(str(claims.get("sub", "")))

    async def _get_upload_record(self, upload_id: str) -> UploadRecord:
        record = await self._session.get(UploadRecord, upload_id)
        if record is None or record.deleted_at is not None:
            raise NotFoundError("Upload record not found after pipeline")
        return record

    async def upload(
        self,
        *,
        data: bytes,
        filename: str,
        meta: IndependentPersonalUploadRequest,
        authentik_id: str,
    ) -> IndependentPersonalUploadResponse:
        """Upload a PDF to the caller's private pool with per-user dedup."""
        user = await self._require_independent_user(authentik_id)
        profile = get_profile(_PROFILE_NAME)
        file_sha256 = sha256_of_bytes(data)

        existing = await self._repo.get_by_user_sha256(user.id, file_sha256)
        if existing is not None:
            if existing.status in (PersonalContentStatus.PENDING, PersonalContentStatus.FAILED):
                self._enqueue_ingestion(existing)
            await audit(
                session=self._session,
                action="independent_personal_content.uploaded",
                actor_id=authentik_id,
                target_type="independent_personal_content",
                target_id=existing.id,
                metadata={"title": existing.title, "storage_deduplicated": True},
            )
            logger.info(
                "independent_personal_upload_deduped",
                content_id=existing.id,
                user_id=user.id,
            )
            return IndependentPersonalUploadResponse(
                item=IndependentPersonalContentRead.model_validate(existing),
                storage_deduplicated=True,
                message="Duplicate file for this user — returning existing private pool entry.",
            )

        try:
            upload_result = await run_upload_pipeline(
                data=data,
                filename=filename,
                profile=profile,
                session=self._session,
                school_id=user.id,
                uploaded_by=authentik_id,
            )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        storage_deduplicated = upload_result.status is UploadStatus.DUPLICATE
        upload_record = await self._get_upload_record(upload_result.upload_id)
        parsing_status = (
            PersonalStructuredParsingStatus.NOT_APPLICABLE
            if meta.content_type == PersonalContentType.REFERENCE.value
            else PersonalStructuredParsingStatus.PENDING
        )

        item = IndependentPersonalContent(
            user_id=user.id,
            content_type=PersonalContentType(meta.content_type),
            title=meta.title.strip(),
            file_key=upload_record.minio_key,
            file_sha256=file_sha256,
            status=PersonalContentStatus.PENDING,
            structured_parsing_status=parsing_status,
            vector_collection=independent_personal_collection(user.id),
        )
        saved = await self._repo.save(item)

        await audit(
            session=self._session,
            action="independent_personal_content.uploaded",
            actor_id=authentik_id,
            target_type="independent_personal_content",
            target_id=saved.id,
            metadata={
                "title": saved.title,
                "storage_deduplicated": storage_deduplicated,
            },
        )

        self._enqueue_ingestion(saved)

        logger.info(
            "independent_personal_upload_created",
            content_id=saved.id,
            user_id=user.id,
        )
        return IndependentPersonalUploadResponse(
            item=IndependentPersonalContentRead.model_validate(saved),
            storage_deduplicated=storage_deduplicated,
        )

    def _enqueue_ingestion(self, item: IndependentPersonalContent) -> None:
        from app.features.library.independent_personal_tasks import (
            ingest_independent_personal_content,
        )

        ingest_independent_personal_content.apply_async(
            args=[item.id, item.user_id],
            queue="ingestion",
        )

    async def list_items(
        self,
        claims: dict[str, object],
        *,
        content_type: str | None = None,
        title: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> IndependentPersonalListResponse:
        user = await self._require_independent_user_from_claims(claims)
        items = await self._repo.list_for_user(
            user.id,
            limit=limit,
            offset=offset,
            content_type=content_type,
            title=title,
        )
        total = await self._repo.count_for_user(
            user.id,
            content_type=content_type,
            title=title,
        )
        return IndependentPersonalListResponse(
            items=[IndependentPersonalContentRead.model_validate(i) for i in items],
            total=total,
        )

    async def get_item(
        self,
        content_id: str,
        claims: dict[str, object],
    ) -> IndependentPersonalContentRead:
        user = await self._require_independent_user_from_claims(claims)
        item = await self._repo.get_by_id(content_id)
        if item is None or item.user_id != user.id or item.deleted_at is not None:
            raise NotFoundError("Private pool item not found")
        return IndependentPersonalContentRead.model_validate(item)
