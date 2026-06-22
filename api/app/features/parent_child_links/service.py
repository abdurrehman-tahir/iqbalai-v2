"""Parent-child link business logic — T-081."""

from __future__ import annotations

from datetime import datetime, timezone

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError, ValidationError
from app.features.independent_users.repository import IndependentUserRepository
from app.features.parent_child_links.models import ParentChildLink, ParentChildLinkStatus
from app.features.parent_child_links.repository import ParentChildLinkRepository
from app.features.parent_child_links.schemas import (
    ParentChildLinkRead,
    ParentConnectionsRead,
    ParentLinkRequestCreate,
    StudentLinkRequestList,
)
from app.features.parent_signup.models import ParentProfile
from app.features.parent_signup.repository import ParentProfileRepository
from app.features.parent_signup.service import (
    PARENT_STATE_ACTIVE_UNLINKED,
    ParentSignupService,
)
from app.features.users.models import User, UserAccountStatus, UserRole
from app.features.users.repository import UserRepository
from app.infrastructure.audit.log import audit
from app.infrastructure.notifications.connections import notify_connections_event

logger = structlog.get_logger(__name__)

PARENT_STATE_LINK_PENDING = "LINK_PENDING"
PARENT_STATE_LINKED = "LINKED"

_LINK_REQUEST_ERROR = (
    "Unable to send link request. Check the student email and try again."
)


class ParentChildLinkService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._links = ParentChildLinkRepository(session)
        self._users = UserRepository(session)
        self._parent_profiles = ParentProfileRepository(session)
        self._independent_users = IndependentUserRepository(session)

    async def _require_parent(self, claims: dict[str, object]) -> tuple[User, ParentProfile]:
        if str(claims.get("role", "")) != UserRole.PARENT.value:
            raise PermissionDeniedError("Parent role required")

        user_id = str(claims.get("user_id", ""))
        user = await self._users.get_by_id(user_id)
        if user is None or user.role != UserRole.PARENT:
            raise PermissionDeniedError("Parent role required")

        profile = await self._parent_profiles.get_by_user_id(user.id)
        if profile is None or not profile.is_email_verified:
            raise ValidationError("Complete parent signup and verify your email before linking")

        return user, profile

    async def _require_student(self, claims: dict[str, object]) -> User:
        if str(claims.get("role", "")) != UserRole.STUDENT.value:
            raise PermissionDeniedError("Student role required")

        user_id = str(claims.get("user_id", ""))
        user = await self._users.get_by_id(user_id)
        if user is None or user.role != UserRole.STUDENT:
            raise PermissionDeniedError("Student role required")
        return user

    @staticmethod
    def _compute_parent_state(
        profile: ParentProfile,
        links: list[ParentChildLink],
    ) -> str:
        if any(link.status == ParentChildLinkStatus.APPROVED for link in links):
            return PARENT_STATE_LINKED
        if any(link.status == ParentChildLinkStatus.PENDING for link in links):
            return PARENT_STATE_LINK_PENDING
        if profile.is_email_verified:
            return PARENT_STATE_ACTIVE_UNLINKED
        return ParentSignupService.parent_state_for_profile(profile)

    async def _resolve_linkable_school_student(self, email: str) -> User | None:
        normalized = email.lower().strip()
        student = await self._users.get_by_email(normalized)
        if student is None:
            return None
        if student.role != UserRole.STUDENT:
            return None
        if student.status not in (UserAccountStatus.ACTIVE, UserAccountStatus.INVITED):
            return None
        if student.deleted_at is not None:
            return None
        return student

    async def _to_link_read(
        self,
        link: ParentChildLink,
        *,
        include_parent: bool = False,
        include_student: bool = False,
    ) -> ParentChildLinkRead:
        parent_name: str | None = None
        student_name: str | None = None
        student_email: str | None = None

        if include_parent:
            parent = await self._users.get_by_id(link.parent_user_id)
            if parent is not None:
                parent_name = parent.display_name

        if include_student:
            student = await self._users.get_by_id(link.student_user_id)
            if student is not None:
                student_name = student.display_name
                student_email = student.email

        return ParentChildLinkRead(
            id=link.id,
            parent_user_id=link.parent_user_id,
            student_user_id=link.student_user_id,
            status=link.status,
            parent_name=parent_name,
            student_name=student_name,
            student_email=student_email,
            approved_at=link.approved_at,
            created_at=link.created_at,
        )

    async def get_parent_connections(self, claims: dict[str, object]) -> ParentConnectionsRead:
        parent, profile = await self._require_parent(claims)
        links = await self._links.list_for_parent(parent.id)
        reads = [
            await self._to_link_read(link, include_student=True) for link in links
        ]
        return ParentConnectionsRead(
            parent_state=self._compute_parent_state(profile, links),
            links=reads,
        )

    async def create_link_request(
        self,
        payload: ParentLinkRequestCreate,
        claims: dict[str, object],
    ) -> ParentChildLinkRead:
        parent, profile = await self._require_parent(claims)
        email = payload.student_email.lower().strip()

        if email == parent.email.lower():
            raise ValidationError(_LINK_REQUEST_ERROR)

        if await self._independent_users.get_by_email(email) is not None:
            raise ValidationError(_LINK_REQUEST_ERROR)

        student = await self._resolve_linkable_school_student(email)
        if student is None:
            raise ValidationError(_LINK_REQUEST_ERROR)

        existing = await self._links.get_by_parent_and_student(
            parent_user_id=parent.id,
            student_user_id=student.id,
        )
        if existing is not None:
            if existing.status == ParentChildLinkStatus.PENDING:
                raise ConflictError("A link request to this student is already pending")
            if existing.status == ParentChildLinkStatus.APPROVED:
                raise ConflictError("You are already linked to this student")
            raise ValidationError(_LINK_REQUEST_ERROR)

        link = ParentChildLink(
            parent_user_id=parent.id,
            student_user_id=student.id,
            status=ParentChildLinkStatus.PENDING,
        )
        created = await self._links.create(link)

        await notify_connections_event(
            session=self._session,
            template_key="connections.parent_link_pending",
            recipient_user_id=student.authentik_id,
            school_id=student.school_id,
            locale=profile.language_preference,
            params={"parent_name": parent.display_name},
            metadata={"link_id": created.id, "parent_user_id": parent.id},
        )

        await audit(
            session=self._session,
            action="parent_link.requested",
            actor_id=parent.authentik_id,
            target_type="parent_child_link",
            target_id=created.id,
            metadata={
                "parent_user_id": parent.id,
                "student_user_id": student.id,
            },
        )
        logger.info(
            "parent_link_requested",
            link_id=created.id,
            parent_user_id=parent.id,
            student_user_id=student.id,
        )
        return await self._to_link_read(created, include_student=True)

    async def list_student_pending_requests(
        self,
        claims: dict[str, object],
    ) -> StudentLinkRequestList:
        student = await self._require_student(claims)
        pending = await self._links.list_pending_for_student(student.id)
        reads = [
            await self._to_link_read(link, include_parent=True) for link in pending
        ]
        return StudentLinkRequestList(pending=reads)

    async def approve_link_request(
        self,
        link_id: str,
        claims: dict[str, object],
    ) -> ParentChildLinkRead:
        student = await self._require_student(claims)
        link = await self._links.get_by_id(link_id)
        if link is None or link.student_user_id != student.id:
            raise NotFoundError("Link request not found")
        if link.status != ParentChildLinkStatus.PENDING:
            raise ConflictError("This link request is no longer pending")

        now = datetime.now(timezone.utc)
        link.status = ParentChildLinkStatus.APPROVED
        link.approved_at = now
        updated = await self._links.update(link)

        parent = await self._users.get_by_id(link.parent_user_id)
        if parent is not None:
            profile = await self._parent_profiles.get_by_user_id(parent.id)
            if profile is not None:
                profile.unlinked_since = None
                await self._parent_profiles.update(profile)

            await notify_connections_event(
                session=self._session,
                template_key="connections.parent_link_approved",
                recipient_user_id=parent.authentik_id,
                school_id=student.school_id,
                locale=profile.language_preference if profile else "en",
                params={"student_name": student.display_name},
                metadata={"link_id": updated.id, "student_user_id": student.id},
            )

        await audit(
            session=self._session,
            action="parent_link.approved",
            actor_id=student.authentik_id,
            target_type="parent_child_link",
            target_id=updated.id,
            metadata={
                "parent_user_id": link.parent_user_id,
                "student_user_id": student.id,
            },
        )
        logger.info(
            "parent_link_approved",
            link_id=updated.id,
            parent_user_id=link.parent_user_id,
            student_user_id=student.id,
        )
        return await self._to_link_read(updated, include_parent=True)

    async def has_approved_link(self, *, parent_user_id: str, student_user_id: str) -> bool:
        link = await self._links.get_by_parent_and_student(
            parent_user_id=parent_user_id,
            student_user_id=student_user_id,
        )
        return link is not None and link.status == ParentChildLinkStatus.APPROVED
