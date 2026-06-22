"""Parent public signup — flow-4 §3.3 / T-080."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ValidationError
from app.features.independent_users.repository import IndependentUserRepository
from app.features.parent_signup.models import ParentProfile
from app.features.parent_signup.repository import ParentProfileRepository
from app.features.parent_signup.schemas import (
    ParentSignupCreate,
    ParentSignupInfo,
    ParentSignupResponse,
)
from app.features.users.models import User, UserAccountStatus, UserRole
from app.features.users.repository import UserRepository
from app.infrastructure.audit.log import audit
from app.infrastructure.authentik.client import AuthentikClientProtocol, get_authentik_client
from app.infrastructure.notifications.email import send_account_email
from app.infrastructure.notifications.templates.account import render_account_template

logger = structlog.get_logger(__name__)

PARENT_USERS_GROUP = "role:parent"
SUPPORTED_LANGUAGES = ("en", "ur", "sd", "ps")
UNLINKED_SUSPEND_DAYS = 90

PARENT_STATE_REGISTERED = "PARENT_REGISTERED"
PARENT_STATE_ACTIVE_UNLINKED = "PARENT_ACTIVE_UNLINKED"


class ParentSignupService:
    def __init__(
        self,
        session: AsyncSession,
        authentik: AuthentikClientProtocol | None = None,
    ) -> None:
        self._session = session
        self._users = UserRepository(session)
        self._profiles = ParentProfileRepository(session)
        self._independent_users = IndependentUserRepository(session)
        self._authentik = authentik or get_authentik_client()

    @staticmethod
    def signup_info() -> ParentSignupInfo:
        return ParentSignupInfo(languages=list(SUPPORTED_LANGUAGES))

    @staticmethod
    def parent_state_for_profile(profile: ParentProfile | None) -> str:
        if profile is None or not profile.is_email_verified:
            return PARENT_STATE_REGISTERED
        return PARENT_STATE_ACTIVE_UNLINKED

    async def _ensure_email_available(self, email: str) -> None:
        normalized = email.lower()
        if await self._users.get_by_email(normalized) is not None:
            raise ConflictError(f"A user with email '{email}' already exists")
        if await self._independent_users.get_by_email(normalized) is not None:
            raise ConflictError(f"A user with email '{email}' already exists")

    async def signup(self, payload: ParentSignupCreate) -> ParentSignupResponse:
        if payload.language_preference not in SUPPORTED_LANGUAGES:
            raise ValidationError(f"Unsupported language: {payload.language_preference}")

        email = payload.email.lower().strip()
        display_name = payload.display_name.strip()
        await self._ensure_email_available(email)

        authentik_id = await self._authentik.create_user(
            email=email,
            name=display_name,
            is_active=False,
        )
        await self._authentik.add_to_group(authentik_id, PARENT_USERS_GROUP)
        await self._authentik.set_password(authentik_id, payload.password)
        await self._authentik.activate_user(authentik_id)

        user = User(
            authentik_id=authentik_id,
            email=email,
            display_name=display_name,
            role=UserRole.PARENT,
            status=UserAccountStatus.ACTIVE,
            school_id=None,
            district_id=None,
        )
        created_user = await self._users.create(user)

        profile = ParentProfile(
            user_id=created_user.id,
            name=display_name,
            language_preference=payload.language_preference,
            is_email_verified=False,
            unlinked_since=None,
        )
        await self._profiles.create(profile)

        welcome = render_account_template(
            "account.parent_welcome",
            locale=payload.language_preference,
            params={"name": display_name},
        )
        await send_account_email(
            to=email,
            subject=welcome.get("subject", "Welcome to IqbalAI"),
            body=welcome.get("body", f"Hi {display_name}, your parent account is ready."),
            template_key="account.parent_welcome",
        )

        await audit(
            session=self._session,
            action="user.parent_signup",
            actor_id=authentik_id,
            target_type="user",
            target_id=created_user.id,
            metadata={"email": email, "role": UserRole.PARENT.value},
        )
        logger.info("parent_signup_completed", user_id=created_user.id, email=email)

        return ParentSignupResponse(
            user_id=created_user.id,
            email=created_user.email,
            role=created_user.role.value,
            tenant_type="school",
            parent_state=PARENT_STATE_REGISTERED,
            message="Account created — verify your email and sign in",
        )

    async def activate_on_login(self, user: User) -> ParentProfile | None:
        """Mark email verified and start the unlinked clock on first login."""
        if user.role != UserRole.PARENT:
            return None

        profile = await self._profiles.get_by_user_id(user.id)
        if profile is None:
            return None

        now = datetime.now(timezone.utc)
        changed = False
        if not profile.is_email_verified:
            profile.is_email_verified = True
            changed = True
        if profile.unlinked_since is None:
            profile.unlinked_since = now
            changed = True

        if changed:
            profile = await self._profiles.update(profile)
            logger.info(
                "parent_activated_on_login",
                user_id=user.id,
                parent_state=self.parent_state_for_profile(profile),
            )
        return profile

    async def try_resume_unlinked_parent(self, user: User) -> User | None:
        """Resume a parent auto-suspended for 90-day unlinked inactivity."""
        if user.role != UserRole.PARENT or user.status != UserAccountStatus.SUSPENDED:
            return None

        profile = await self._profiles.get_by_user_id(user.id)
        if profile is None or profile.unlinked_since is None:
            return None

        user.status = UserAccountStatus.ACTIVE
        profile.unlinked_since = datetime.now(timezone.utc)
        await self._users.update(user)
        await self._profiles.update(profile)
        logger.info("parent_unlinked_auto_suspend_resumed", user_id=user.id)
        return user

    async def suspend_stale_unlinked_parents(self) -> int:
        """Auto-suspend parents unlinked for 90+ days. Returns count suspended."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=UNLINKED_SUSPEND_DAYS)
        stale = await self._profiles.list_stale_unlinked(cutoff)
        count = 0

        for user, profile in stale:
            user.status = UserAccountStatus.SUSPENDED
            await self._users.update(user)

            rendered = render_account_template(
                "account.parent_auto_suspended",
                locale=profile.language_preference,
                params={"name": profile.name},
            )
            await send_account_email(
                to=user.email,
                subject=rendered.get("subject", "IqbalAI parent account suspended"),
                body=rendered.get("body", ""),
                template_key="account.parent_auto_suspended",
            )
            count += 1
            logger.info("parent_unlinked_auto_suspended", user_id=user.id, email=user.email)

        return count
