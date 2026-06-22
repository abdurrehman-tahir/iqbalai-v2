"""Independent user signup — public Path B per ARCH §6.20."""

from __future__ import annotations

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ValidationError
from app.features.exam_syllabi.repository import ExamSyllabiRepository
from app.features.independent_signup.schemas import (
    IndependentSignupCreate,
    IndependentSignupInfo,
    IndependentSignupResponse,
)
from app.features.independent_student_onboarding.models import IndependentStudentProfile
from app.features.independent_student_onboarding.repository import IndependentStudentProfileRepository
from app.features.independent_users.models import (
    IndependentUser,
    IndependentUserAccountStatus,
    IndependentUserRole,
)
from app.features.independent_users.repository import IndependentUserRepository
from app.features.users.repository import UserRepository
from app.infrastructure.audit.log import audit
from app.infrastructure.authentik.client import AuthentikClientProtocol, get_authentik_client
from app.infrastructure.notifications.email import send_account_email

logger = structlog.get_logger(__name__)

INDEPENDENT_USERS_GROUP = "role:independent"
SUPPORTED_LANGUAGES = ("en", "ur", "sd", "ps")


class IndependentSignupService:
    def __init__(
        self,
        session: AsyncSession,
        authentik: AuthentikClientProtocol | None = None,
    ) -> None:
        self._session = session
        self._independent_users = IndependentUserRepository(session)
        self._student_profiles = IndependentStudentProfileRepository(session)
        self._syllabi = ExamSyllabiRepository(session)
        self._school_users = UserRepository(session)
        self._authentik = authentik or get_authentik_client()

    def get_signup_info(self) -> IndependentSignupInfo:
        return IndependentSignupInfo(
            roles=[
                IndependentUserRole.INDEPENDENT_TEACHER.value,
                IndependentUserRole.INDEPENDENT_STUDENT.value,
            ],
            languages=list(SUPPORTED_LANGUAGES),
        )

    @staticmethod
    def signup_info() -> IndependentSignupInfo:
        return IndependentSignupInfo(
            roles=[
                IndependentUserRole.INDEPENDENT_TEACHER.value,
                IndependentUserRole.INDEPENDENT_STUDENT.value,
            ],
            languages=list(SUPPORTED_LANGUAGES),
        )

    async def _ensure_email_available(self, email: str) -> None:
        normalized = email.lower()
        if await self._school_users.get_by_email(normalized) is not None:
            raise ConflictError(f"A user with email '{email}' already exists")
        if await self._independent_users.get_by_email(normalized) is not None:
            raise ConflictError(f"A user with email '{email}' already exists")

    async def signup(self, payload: IndependentSignupCreate) -> IndependentSignupResponse:
        if payload.role not in (
            IndependentUserRole.INDEPENDENT_TEACHER,
            IndependentUserRole.INDEPENDENT_STUDENT,
        ):
            raise ValidationError("Invalid role for independent signup")

        if payload.language_preference not in SUPPORTED_LANGUAGES:
            raise ValidationError(f"Unsupported language: {payload.language_preference}")

        if payload.role == IndependentUserRole.INDEPENDENT_STUDENT:
            if payload.grade_level is None:
                raise ValidationError("grade_level is required for independent student signup")
            if not payload.exam_syllabus_id:
                raise ValidationError("exam_syllabus_id is required for independent student signup")
            syllabus = await self._syllabi.get_by_id(payload.exam_syllabus_id)
            if syllabus is None or syllabus.deleted_at is not None or not syllabus.is_active:
                raise ValidationError("Invalid or inactive exam framework selection")

        email = payload.email.lower().strip()
        display_name = payload.display_name.strip()
        await self._ensure_email_available(email)

        authentik_id = await self._authentik.create_user(
            email=email,
            name=display_name,
            is_active=False,
        )
        await self._authentik.add_to_group(authentik_id, INDEPENDENT_USERS_GROUP)
        await self._authentik.add_to_group(authentik_id, f"role:{payload.role.value}")
        await self._authentik.set_password(authentik_id, payload.password)
        await self._authentik.activate_user(authentik_id)

        user = IndependentUser(
            authentik_id=authentik_id,
            email=email,
            display_name=display_name,
            role=payload.role,
            status=IndependentUserAccountStatus.ACTIVE,
            language_preference=payload.language_preference,
        )
        created = await self._independent_users.create(user)

        if payload.role == IndependentUserRole.INDEPENDENT_STUDENT:
            assert payload.grade_level is not None
            assert payload.exam_syllabus_id is not None
            student_profile = IndependentStudentProfile(
                user_id=created.id,
                name=display_name,
                language_preference=payload.language_preference,
                grade_level=payload.grade_level,
                exam_syllabus_id=payload.exam_syllabus_id,
            )
            await self._student_profiles.create(student_profile)

        await send_account_email(
            to=email,
            subject="Welcome to IqbalAI — your account is ready",
            body=(
                f"Hi {display_name},\n\n"
                "Your IqbalAI independent account has been created. "
                "Sign in at the app login page with your email and password.\n"
            ),
            template_key="account.independent_signup_welcome",
        )

        await audit(
            session=self._session,
            action="user.independent_signup",
            actor_id=authentik_id,
            target_type="independent_user",
            target_id=created.id,
            metadata={"email": email, "role": payload.role.value},
        )
        logger.info(
            "independent_signup_completed",
            user_id=created.id,
            email=email,
            role=payload.role.value,
        )
        return IndependentSignupResponse(
            user_id=created.id,
            email=created.email,
            role=created.role.value,
            tenant_type="independent",
            message="Account created — sign in to continue",
        )
