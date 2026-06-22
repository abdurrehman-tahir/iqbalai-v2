"""Data rights business logic — T-084."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError, ValidationError
from app.features.data_rights.export_builder import build_export_zip
from app.features.data_rights.models import (
    DataRightsRequest,
    DataRightsRequestStatus,
    DataRightsRequestType,
)
from app.features.data_rights.repository import DataRightsRequestRepository
from app.features.data_rights.schemas import DataRightsRequestRead, DataRightsStatusRead
from app.features.parent_child_links.repository import ParentChildLinkRepository
from app.features.parent_signup.models import ParentProfile
from app.features.parent_signup.repository import ParentProfileRepository
from app.features.student_enrollments.repository import StudentEnrollmentRepository
from app.features.student_onboarding.models import StudentProfile
from app.features.student_onboarding.repository import StudentProfileRepository
from app.features.users.models import User, UserRole
from app.features.users.repository import UserRepository
from app.infrastructure.audit.log import audit
from app.infrastructure.notifications.account import notify_account_event
from app.infrastructure.storage.client import download_bytes, upload_bytes

logger = structlog.get_logger(__name__)

EXPORT_DOWNLOAD_DAYS = 7
DELETION_GRACE_DAYS = 30

EXPORT_POLICY_MESSAGE = (
    "Request a copy of your personal data. We prepare a machine-readable ZIP within 24 hours. "
    "Downloads stay available for 7 days. The bundle includes only your data — never other users'."
)

DELETION_POLICY_MESSAGE = (
    "Account deletion requests enter a 30-day grace period and are queued for review. "
    "We do not hard-delete immediately because audit records must be retained for 7 years. "
    "You may cancel during the grace period."
)


class DataRightsService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._requests = DataRightsRequestRepository(session)
        self._users = UserRepository(session)
        self._student_profiles = StudentProfileRepository(session)
        self._parent_profiles = ParentProfileRepository(session)
        self._links = ParentChildLinkRepository(session)
        self._enrollments = StudentEnrollmentRepository(session)

    async def _require_user(self, claims: dict[str, object], *, role: UserRole) -> User:
        authentik_id = str(claims.get("sub", ""))
        user = await self._users.get_by_authentik_id(authentik_id)
        if user is None or user.role != role:
            raise PermissionDeniedError()
        return user

    @staticmethod
    def _to_read(request: DataRightsRequest) -> DataRightsRequestRead:
        now = datetime.now(timezone.utc)
        download_available = (
            request.request_type == DataRightsRequestType.EXPORT
            and request.status == DataRightsRequestStatus.READY
            and request.file_key is not None
            and (request.expires_at is None or request.expires_at > now)
        )
        return DataRightsRequestRead(
            id=request.id,
            request_type=request.request_type,
            status=request.status,
            requested_at=request.requested_at,
            ready_at=request.ready_at,
            expires_at=request.expires_at,
            deletion_scheduled_at=request.deletion_scheduled_at,
            completed_at=request.completed_at,
            cancelled_at=request.cancelled_at,
            download_available=download_available,
        )

    async def get_status(self, claims: dict[str, object], *, role: UserRole) -> DataRightsStatusRead:
        user = await self._require_user(claims, role=role)
        await self._expire_stale_exports(user.id)
        requests = await self._requests.list_for_user(user.id)
        export_request = next(
            (self._to_read(r) for r in requests if r.request_type == DataRightsRequestType.EXPORT),
            None,
        )
        deletion_request = next(
            (self._to_read(r) for r in requests if r.request_type == DataRightsRequestType.DELETION),
            None,
        )
        return DataRightsStatusRead(
            export_request=export_request,
            deletion_request=deletion_request,
            export_policy_message=EXPORT_POLICY_MESSAGE,
            deletion_policy_message=DELETION_POLICY_MESSAGE,
        )

    async def request_export(
        self,
        claims: dict[str, object],
        *,
        role: UserRole,
        actor_id: str,
    ) -> DataRightsRequestRead:
        user = await self._require_user(claims, role=role)
        await self._expire_stale_exports(user.id)
        active = await self._requests.get_active_export(user.id)
        if active is not None:
            raise ConflictError("An export is already in progress or ready to download.")

        now = datetime.now(timezone.utc)
        request = DataRightsRequest(
            user_id=user.id,
            request_type=DataRightsRequestType.EXPORT,
            status=DataRightsRequestStatus.REQUESTED,
            requested_at=now,
        )
        await self._requests.create(request)
        await self._session.commit()

        await audit(
            session=self._session,
            action="data_rights.export_requested",
            actor_id=actor_id,
            actor_role=role.value,
            target_type="data_rights_request",
            target_id=request.id,
            school_id=user.school_id,
            metadata={"request_type": "export", "flagged": True},
        )

        from app.features.data_rights.tasks import process_data_export

        process_data_export.delay(request.id)

        return self._to_read(request)

    async def download_export(
        self,
        request_id: str,
        claims: dict[str, object],
        *,
        role: UserRole,
    ) -> tuple[bytes, str]:
        user = await self._require_user(claims, role=role)
        await self._expire_stale_exports(user.id)
        request = await self._requests.get_for_user(request_id=request_id, user_id=user.id)
        if request is None or request.request_type != DataRightsRequestType.EXPORT:
            raise NotFoundError("Export not found.")
        if request.status != DataRightsRequestStatus.READY or not request.file_key:
            raise ValidationError("Export is not ready for download yet.")
        if request.expires_at and request.expires_at <= datetime.now(timezone.utc):
            raise ValidationError("Export download window has expired. Request a new export.")

        settings = get_settings()
        data = download_bytes(settings.MINIO_BUCKET_EXPORTS, request.file_key)
        filename = f"iqbalai-export-{request.id[:8]}.zip"
        return data, filename

    async def request_deletion(
        self,
        claims: dict[str, object],
        *,
        role: UserRole,
        actor_id: str,
        confirmed: bool,
    ) -> DataRightsRequestRead:
        if not confirmed:
            raise ValidationError("You must confirm the deletion request.")

        user = await self._require_user(claims, role=role)
        active = await self._requests.get_active_deletion(user.id)
        if active is not None:
            raise ConflictError("A deletion request is already in the grace period.")

        now = datetime.now(timezone.utc)
        scheduled = now + timedelta(days=DELETION_GRACE_DAYS)
        request = DataRightsRequest(
            user_id=user.id,
            request_type=DataRightsRequestType.DELETION,
            status=DataRightsRequestStatus.GRACE_PERIOD,
            requested_at=now,
            deletion_scheduled_at=scheduled,
        )
        await self._requests.create(request)
        await self._session.commit()

        await audit(
            session=self._session,
            action="data_rights.deletion_requested",
            actor_id=actor_id,
            actor_role=role.value,
            target_type="data_rights_request",
            target_id=request.id,
            school_id=user.school_id,
            metadata={
                "deletion_scheduled_at": scheduled.isoformat(),
                "queued_for_review": True,
                "flagged": True,
            },
        )

        profile = await self._profile_for_user(user)
        locale = profile.language_preference if profile else "en"
        await notify_account_event(
            session=self._session,
            template_key="account.deletion_grace_started",
            locale=locale,
            recipient_user_id=user.authentik_id,
            recipient_email=user.email,
            school_id=user.school_id,
            params={
                "name": user.display_name,
                "scheduled_date": scheduled.date().isoformat(),
            },
        )

        return self._to_read(request)

    async def cancel_deletion(
        self,
        request_id: str,
        claims: dict[str, object],
        *,
        role: UserRole,
        actor_id: str,
    ) -> DataRightsRequestRead:
        user = await self._require_user(claims, role=role)
        request = await self._requests.get_for_user(request_id=request_id, user_id=user.id)
        if request is None or request.request_type != DataRightsRequestType.DELETION:
            raise NotFoundError("Deletion request not found.")
        if request.status != DataRightsRequestStatus.GRACE_PERIOD:
            raise ValidationError("Only an active grace-period deletion can be cancelled.")

        now = datetime.now(timezone.utc)
        request.status = DataRightsRequestStatus.CANCELLED
        request.cancelled_at = now
        await self._requests.update(request)
        await self._session.commit()

        await audit(
            session=self._session,
            action="data_rights.deletion_cancelled",
            actor_id=actor_id,
            actor_role=role.value,
            target_type="data_rights_request",
            target_id=request.id,
            school_id=user.school_id,
            metadata={"flagged": True},
        )

        return self._to_read(request)

    async def process_export_request(self, request_id: str) -> None:
        request = await self._requests.get_by_id(request_id)
        if request is None or request.request_type != DataRightsRequestType.EXPORT:
            logger.warning("data_export_missing_request", request_id=request_id)
            return
        if request.status not in {
            DataRightsRequestStatus.REQUESTED,
            DataRightsRequestStatus.PROCESSING,
        }:
            return

        request.status = DataRightsRequestStatus.PROCESSING
        await self._requests.update(request)
        await self._session.commit()

        user = await self._users.get_by_id(request.user_id)
        if user is None:
            logger.error("data_export_user_missing", request_id=request_id)
            return

        student_profile: StudentProfile | None = None
        parent_profile: ParentProfile | None = None
        student_links = None
        parent_links = None
        enrollments = None
        if user.role == UserRole.STUDENT:
            student_profile = await self._student_profiles.get_by_user_id(user.id)
            student_links = await self._links.list_for_student(user.id)
            enrollments = await self._enrollments.list_for_student(user.id)
        elif user.role == UserRole.PARENT:
            parent_profile = await self._parent_profiles.get_by_user_id(user.id)
            parent_links = await self._links.list_for_parent(user.id)

        bundle = build_export_zip(
            user=user,
            student_profile=student_profile,
            parent_profile=parent_profile,
            student_links=student_links if user.role == UserRole.STUDENT else None,
            parent_links=parent_links if user.role == UserRole.PARENT else None,
            enrollments=enrollments if user.role == UserRole.STUDENT else None,
        )

        settings = get_settings()
        file_key = f"exports/{user.id}/{request.id}.zip"
        upload_bytes(
            settings.MINIO_BUCKET_EXPORTS,
            file_key,
            bundle,
            content_type="application/zip",
        )

        now = datetime.now(timezone.utc)
        request.status = DataRightsRequestStatus.READY
        request.ready_at = now
        request.expires_at = now + timedelta(days=EXPORT_DOWNLOAD_DAYS)
        request.file_key = file_key
        await self._requests.update(request)
        await self._session.commit()

        profile = await self._profile_for_user(user)
        locale = profile.language_preference if profile else "en"
        await notify_account_event(
            session=self._session,
            template_key="account.export_ready",
            locale=locale,
            recipient_user_id=user.authentik_id,
            recipient_email=user.email,
            school_id=user.school_id,
            params={"name": user.display_name},
            metadata={"request_id": request.id},
        )

        logger.info("data_export_ready", request_id=request.id, user_id=user.id)

    async def _expire_stale_exports(self, user_id: str) -> None:
        requests = await self._requests.list_for_user(user_id)
        now = datetime.now(timezone.utc)
        changed = False
        for request in requests:
            if (
                request.request_type == DataRightsRequestType.EXPORT
                and request.status == DataRightsRequestStatus.READY
                and request.expires_at
                and request.expires_at <= now
            ):
                request.status = DataRightsRequestStatus.EXPIRED
                changed = True
        if changed:
            await self._session.commit()

    async def _profile_for_user(self, user: User) -> StudentProfile | ParentProfile | None:
        if user.role == UserRole.STUDENT:
            return await self._student_profiles.get_by_user_id(user.id)
        if user.role == UserRole.PARENT:
            return await self._parent_profiles.get_by_user_id(user.id)
        return None
