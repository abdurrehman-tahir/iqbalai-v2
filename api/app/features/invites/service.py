"""User invitation service — Path A admin invite flow (T-030)."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import (
    ConflictError,
    NotFoundError,
    PreconditionFailedError,
    ValidationError,
)
from app.features.invites.models import UserInvite, UserInviteStatus
from app.features.invites.repository import UserInviteRepository
from app.features.invites.schemas import AcceptInviteRequest, AdminUserInviteCreate
from app.features.schools.repository import DistrictRepository, SchoolRepository
from app.features.users.models import User, UserAccountStatus, UserRole
from app.features.users.repository import UserRepository
from app.infrastructure.audit.log import audit
from app.infrastructure.authentik.client import AuthentikClientProtocol, get_authentik_client
from app.infrastructure.cache.client import get_redis
from app.infrastructure.notifications.email import send_invite_email

logger = structlog.get_logger(__name__)

INVITE_TTL_DAYS = 7
LOCKOUT_REJECT_COUNT = 3
LOCKOUT_DAYS = 30
MAX_INVITES_PER_DAY = 200


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


def _new_token_pair() -> tuple[str, str]:
    raw = secrets.token_urlsafe(32)
    return raw, _hash_token(raw)


class InviteService:
    def __init__(
        self,
        session: AsyncSession,
        authentik: AuthentikClientProtocol | None = None,
    ) -> None:
        self._session = session
        self._repo = UserInviteRepository(session)
        self._users = UserRepository(session)
        self._districts = DistrictRepository(session)
        self._schools = SchoolRepository(session)
        self._authentik = authentik or get_authentik_client()

    async def _check_rate_limit(self, actor_id: str) -> None:
        redis = get_redis()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        key = f"invites:{actor_id}:{today}"
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, 86_400)
        if count > MAX_INVITES_PER_DAY:
            raise PreconditionFailedError(
                f"Daily invite limit reached ({MAX_INVITES_PER_DAY} per admin)"
            )

    def _validate_role_scope(self, payload: AdminUserInviteCreate, caller_role: str) -> None:
        if payload.role == UserRole.DISTRICT_ADMIN:
            if caller_role not in ("platform_admin",):
                raise ValidationError("Only Platform Admin may invite District Admin")
            if not payload.district_id:
                raise ValidationError("district_id is required for district_admin invites")
        elif payload.role == UserRole.SCHOOL_ADMIN:
            if caller_role not in ("platform_admin", "district_admin"):
                raise ValidationError("Insufficient role to invite School Admin")
            if not payload.school_id:
                raise ValidationError("school_id is required for school_admin invites")
        else:
            raise ValidationError(
                f"Role '{payload.role.value}' is not inviteable via this endpoint"
            )

    async def _validate_school_for_invite(
        self,
        school_id: str,
        claims: dict[str, object],
        caller_role: str,
    ) -> str:
        """Return the school's district_id; 404 when school missing or out of scope."""
        school = await self._schools.get_by_id(school_id)
        if school is None or school.deleted_at is not None:
            raise NotFoundError(f"School '{school_id}' not found")

        if caller_role == "district_admin":
            caller_district = str(claims.get("district_id", "") or "")
            if caller_district != school.district_id:
                raise NotFoundError("School not found")
        return school.district_id

    async def create_invite(
        self,
        payload: AdminUserInviteCreate,
        actor_id: str,
        caller_role: str,
        claims: dict[str, object],
    ) -> tuple[UserInvite, str]:
        """Create Authentik user (inactive), persist invite, send email."""
        self._validate_role_scope(payload, caller_role)
        await self._check_rate_limit(actor_id)

        email = payload.email.lower()

        existing_user = await self._users.get_by_email(email)
        if existing_user is not None:
            raise ConflictError(f"A user with email '{email}' already exists")

        pending = await self._repo.get_pending_by_email(email)
        if pending is not None:
            raise ConflictError(f"A pending invite already exists for '{email}' — resend instead")

        district_id = payload.district_id
        school_id = payload.school_id
        if payload.role == UserRole.SCHOOL_ADMIN:
            if not school_id:
                raise ValidationError("school_id is required for school_admin invites")
            district_id = await self._validate_school_for_invite(
                school_id, claims, caller_role
            )
        elif payload.district_id:
            district = await self._districts.get_by_id(payload.district_id)
            if district is None or district.deleted_at is not None:
                raise NotFoundError(f"District '{payload.district_id}' not found")

        raw_token, token_hash = _new_token_pair()
        expires_at = datetime.now(timezone.utc) + timedelta(days=INVITE_TTL_DAYS)

        authentik_id = await self._authentik.create_user(
            email=email,
            name=payload.display_name,
            is_active=False,
        )
        await self._authentik.add_to_group(authentik_id, f"role:{payload.role.value}")

        invite = UserInvite(
            email=email,
            display_name=payload.display_name,
            invited_by_user_id=actor_id,
            invited_role=payload.role,
            district_id=district_id,
            school_id=school_id,
            token_hash=token_hash,
            authentik_id=authentik_id,
            expires_at=expires_at,
            status=UserInviteStatus.PENDING,
        )
        created = await self._repo.create(invite)

        settings = get_settings()
        invite_url = f"{settings.APP_URL}/accept-invite?token={raw_token}"
        await send_invite_email(
            to=email,
            invite_url=invite_url,
            inviter_name=payload.display_name,
        )

        await audit(
            session=self._session,
            action="user.invite_sent",
            actor_id=actor_id,
            target_type="user_invite",
            target_id=created.id,
            district_id=district_id,
            school_id=school_id,
            metadata={"email": email, "role": payload.role.value},
        )
        logger.info("user_invite_sent", invite_id=created.id, email=email, by=actor_id)
        return created, raw_token

    async def resend_invite(self, invite_id: str, actor_id: str) -> tuple[UserInvite, str]:
        """Issue a fresh 7-day token for a pending or expired invite."""
        invite = await self._repo.get_by_id(invite_id)
        if invite is None:
            raise NotFoundError(f"Invite '{invite_id}' not found")

        if invite.status == UserInviteStatus.LOCKED:
            locked_until = invite.locked_until
            if locked_until and locked_until > datetime.now(timezone.utc):
                raise PreconditionFailedError(
                    "Invite is locked after 3 rejections — resend allowed after lockout expires"
                )
            invite.status = UserInviteStatus.PENDING
            invite.rejected_count = 0
            invite.locked_until = None

        if invite.status == UserInviteStatus.ACCEPTED:
            raise ConflictError("Invite already accepted")

        if invite.status not in (
            UserInviteStatus.PENDING,
            UserInviteStatus.EXPIRED,
            UserInviteStatus.REJECTED,
        ):
            raise ValidationError(f"Cannot resend invite in status '{invite.status.value}'")

        raw_token, token_hash = _new_token_pair()
        invite.token_hash = token_hash
        invite.expires_at = datetime.now(timezone.utc) + timedelta(days=INVITE_TTL_DAYS)
        invite.status = UserInviteStatus.PENDING
        invite.resent_count += 1
        updated = await self._repo.update(invite)

        settings = get_settings()
        invite_url = f"{settings.APP_URL}/accept-invite?token={raw_token}"
        await send_invite_email(
            to=invite.email,
            invite_url=invite_url,
            inviter_name=invite.display_name,
        )

        await audit(
            session=self._session,
            action="user.invite_resent",
            actor_id=actor_id,
            target_type="user_invite",
            target_id=invite.id,
            district_id=invite.district_id,
            metadata={"email": invite.email, "resent_count": invite.resent_count},
        )
        return updated, raw_token

    async def accept_invite(self, payload: AcceptInviteRequest) -> dict[str, str]:
        """Accept or reject an invitation by token."""
        token_hash = _hash_token(payload.token)
        invite = await self._repo.get_by_token_hash(token_hash)
        if invite is None:
            raise NotFoundError("Invalid or unknown invitation token")

        invite = await self._repo.expire_stale_pending(invite)

        if invite.status == UserInviteStatus.EXPIRED or (
            invite.status == UserInviteStatus.PENDING
            and invite.expires_at < datetime.now(timezone.utc)
        ):
            invite.status = UserInviteStatus.EXPIRED
            await self._repo.update(invite)
            raise ValidationError("Invitation has expired — ask your administrator to resend")

        if invite.status == UserInviteStatus.LOCKED:
            locked_until = invite.locked_until
            if locked_until and locked_until > datetime.now(timezone.utc):
                raise PreconditionFailedError(
                    "Invitation locked after multiple rejections — contact your administrator"
                )

        if invite.status == UserInviteStatus.ACCEPTED:
            raise ConflictError("Invitation already accepted")

        if invite.status != UserInviteStatus.PENDING:
            raise ValidationError(f"Invitation is not actionable (status={invite.status.value})")

        if payload.action == "reject":
            invite.rejected_count += 1
            invite.rejected_at = datetime.now(timezone.utc)
            if invite.rejected_count >= LOCKOUT_REJECT_COUNT:
                invite.status = UserInviteStatus.LOCKED
                invite.locked_until = datetime.now(timezone.utc) + timedelta(days=LOCKOUT_DAYS)
            else:
                invite.status = UserInviteStatus.REJECTED
            await self._repo.update(invite)
            await audit(
                session=self._session,
                action="user.invite_rejected",
                actor_id=invite.authentik_id,
                target_type="user_invite",
                target_id=invite.id,
                district_id=invite.district_id,
                metadata={"email": invite.email, "rejected_count": invite.rejected_count},
            )
            return {
                "status": invite.status.value,
                "message": "Invitation declined",
            }

        if not payload.password:
            raise ValidationError("password is required to accept an invitation")

        if not invite.authentik_id:
            raise ValidationError("Invite is missing Authentik user reference")

        await self._authentik.set_password(invite.authentik_id, payload.password)
        await self._authentik.activate_user(invite.authentik_id)

        display_name = payload.display_name or invite.display_name
        user = User(
            authentik_id=invite.authentik_id,
            email=invite.email,
            display_name=display_name,
            role=invite.invited_role,
            status=UserAccountStatus.ACTIVE,
            district_id=invite.district_id,
            school_id=invite.school_id,
        )
        await self._users.create(user)

        invite.status = UserInviteStatus.ACCEPTED
        invite.accepted_at = datetime.now(timezone.utc)
        await self._repo.update(invite)

        await audit(
            session=self._session,
            action="user.invite_accepted",
            actor_id=invite.authentik_id,
            target_type="user_invite",
            target_id=invite.id,
            district_id=invite.district_id,
            school_id=invite.school_id,
            metadata={"email": invite.email, "role": invite.invited_role.value},
        )
        logger.info("user_invite_accepted", invite_id=invite.id, email=invite.email)
        return {
            "status": "accepted",
            "email": invite.email,
            "message": "Account activated — you can now sign in",
        }
