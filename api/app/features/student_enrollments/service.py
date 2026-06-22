"""Student enrollment service — Coordinator-driven enrollment (T-077)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.features.grades.scope import assert_grade_in_scope
from app.features.grades.service import GradeService
from app.features.independent_users.repository import IndependentUserRepository
from app.features.invites.models import UserInvite, UserInviteStatus
from app.features.invites.repository import UserInviteRepository
from app.features.invites.service import INVITE_TTL_DAYS, _new_token_pair
from app.features.sections.models import Section, SectionStatus
from app.features.sections.repository import SectionRepository
from app.features.student_enrollments.models import StudentEnrollment, StudentEnrollmentStatus
from app.features.student_enrollments.repository import StudentEnrollmentRepository
from app.features.student_enrollments.schemas import StudentEnrollmentCreate
from app.features.users.models import User, UserAccountStatus, UserRole
from app.features.users.repository import UserRepository
from app.infrastructure.audit.log import audit
from app.infrastructure.authentik.client import AuthentikClientProtocol, get_authentik_client
from app.infrastructure.notifications.account import notify_account_event
from app.infrastructure.notifications.email import send_invite_email

logger = structlog.get_logger(__name__)


class StudentEnrollmentService:
    def __init__(
        self,
        session: AsyncSession,
        authentik: AuthentikClientProtocol | None = None,
    ) -> None:
        self._session = session
        self._repo = StudentEnrollmentRepository(session)
        self._users = UserRepository(session)
        self._independent_users = IndependentUserRepository(session)
        self._invites = UserInviteRepository(session)
        self._sections = SectionRepository(session)
        self._grade_svc = GradeService(session)
        self._authentik = authentik or get_authentik_client()

    async def _ensure_email_available(self, email: str) -> None:
        normalized = email.lower()
        if await self._users.get_by_email(normalized) is not None:
            raise ConflictError(f"A user with email '{email}' already exists")
        if await self._independent_users.get_by_email(normalized) is not None:
            raise ConflictError(f"A user with email '{email}' already exists")
        pending = await self._invites.get_pending_by_email(normalized)
        if pending is not None:
            raise ConflictError(f"A pending invite already exists for '{email}'")

    async def _resolve_section(self, grade_id: str, section_id: str | None) -> Section:
        if section_id:
            section = await self._sections.get_by_id(section_id)
            if (
                section is None
                or section.deleted_at is not None
                or section.grade_id != grade_id
                or section.status != SectionStatus.ACTIVE
            ):
                raise NotFoundError(f"Section '{section_id}' not found")
            return section

        rows = await self._sections.list_by_grade(grade_id)
        default = next((s for s in rows if s.is_default_internal), None)
        if default is None:
            raise ValidationError(
                "No default section exists for this grade — create a section or retry"
            )
        return default

    async def enroll_student(
        self,
        grade_id: str,
        payload: StudentEnrollmentCreate,
        claims: dict[str, object],
        actor_id: str,
    ) -> tuple[StudentEnrollment, User]:
        grade = await self._grade_svc.get_grade(grade_id, claims)
        actor = await self._grade_svc._load_actor(claims)
        assert_grade_in_scope(actor, grade.name)

        section = await self._resolve_section(grade_id, payload.section_id)
        email = payload.email.lower()
        await self._ensure_email_available(email)

        raw_token, token_hash = _new_token_pair()
        expires_at = datetime.now(timezone.utc) + timedelta(days=INVITE_TTL_DAYS)
        enrolled_at = datetime.now(timezone.utc)

        authentik_id = await self._authentik.create_user(
            email=email,
            name=payload.display_name,
            is_active=False,
        )
        await self._authentik.add_to_group(authentik_id, "role:student")

        student = User(
            authentik_id=authentik_id,
            email=email,
            display_name=payload.display_name,
            role=UserRole.STUDENT,
            status=UserAccountStatus.INVITED,
            school_id=grade.school_id,
        )
        created_student = await self._users.create(student)

        existing_enrollment = await self._repo.get_active_by_student_session(
            created_student.id, grade.academic_session
        )
        if existing_enrollment is not None:
            raise ConflictError(
                "Student already has an active enrollment for this academic session"
            )

        enrollment = StudentEnrollment(
            school_id=grade.school_id,
            student_user_id=created_student.id,
            grade_id=grade_id,
            section_id=section.id,
            academic_session=grade.academic_session,
            status=StudentEnrollmentStatus.ACTIVE,
            enrolled_at=enrolled_at,
        )
        created_enrollment = await self._repo.create(enrollment)

        invite = UserInvite(
            email=email,
            display_name=payload.display_name,
            invited_by_user_id=actor_id,
            invited_role=UserRole.STUDENT,
            school_id=grade.school_id,
            scope_ids_json={
                "enrollment_id": created_enrollment.id,
                "grade_id": grade_id,
                "section_id": section.id,
            },
            token_hash=token_hash,
            authentik_id=authentik_id,
            expires_at=expires_at,
            status=UserInviteStatus.PENDING,
        )
        await self._invites.create(invite)

        settings = get_settings()
        invite_url = f"{settings.APP_URL}/accept-invite?token={raw_token}"
        await send_invite_email(
            to=email,
            invite_url=invite_url,
            inviter_name=payload.display_name,
        )
        await notify_account_event(
            session=self._session,
            template_key="account.student_invited",
            locale="en",
            recipient_user_id=authentik_id,
            recipient_email=email,
            school_id=grade.school_id,
            params={
                "name": payload.display_name,
                "school_name": grade.school_id,
                "invite_url": invite_url,
            },
        )

        await audit(
            session=self._session,
            action="student.enrolled",
            actor_id=actor_id,
            target_type="student_enrollment",
            target_id=created_enrollment.id,
            school_id=grade.school_id,
            metadata={
                "email": email,
                "grade_id": grade_id,
                "section_id": section.id,
                "academic_session": grade.academic_session,
            },
        )
        logger.info(
            "student_enrolled",
            enrollment_id=created_enrollment.id,
            student_id=created_student.id,
            grade_id=grade_id,
            section_id=section.id,
        )
        return created_enrollment, created_student
