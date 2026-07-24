"""User service — business logic."""

from __future__ import annotations

from datetime import datetime, timezone

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.users.models import User, UserAccountStatus, UserRole
from app.features.users.repository import UserRepository

logger = structlog.get_logger(__name__)

_ROLE_LOGIN_PRIORITY: dict[UserRole, int] = {
    UserRole.PLATFORM_ADMIN: 70,
    UserRole.DISTRICT_ADMIN: 60,
    UserRole.SCHOOL_ADMIN: 50,
    UserRole.COORDINATOR: 40,
    UserRole.TEACHER: 30,
    UserRole.PARENT: 20,
    UserRole.STUDENT: 10,
}


def parse_user_role(role_claim: object) -> UserRole:
    """Map JWT role claim to UserRole (accepts value or enum member name)."""
    if isinstance(role_claim, UserRole):
        return role_claim
    raw = str(role_claim or "student").strip()
    try:
        return UserRole(raw)
    except ValueError:
        pass
    try:
        return UserRole[raw.upper()]
    except KeyError:
        return UserRole.STUDENT


class UserService:
    """Business logic for user management."""

    def __init__(self, session: AsyncSession) -> None:
        self._repo = UserRepository(session)

    async def get_by_authentik_id_any(self, authentik_id: str) -> User | None:
        return await self._repo.get_by_authentik_id_any(authentik_id)

    def _pick_login_user_for_email(self, users: list[User]) -> User:
        """Prefer the invited/admin row when duplicate email rows exist."""
        return max(users, key=lambda user: _ROLE_LOGIN_PRIORITY.get(user.role, 0))

    async def _reconcile_authentik_id_by_email(
        self, *, authentik_id: str, email: str
    ) -> User | None:
        """Link an invited user row when Authentik JWT sub differs from stored API pk."""
        matches = await self._repo.list_by_email(email)
        if not matches:
            return None

        primary = self._pick_login_user_for_email(matches)
        if primary.authentik_id != authentik_id:
            primary.authentik_id = authentik_id
            primary = await self._repo.update(primary)
            logger.info(
                "user_authentik_id_reconciled",
                user_id=primary.id,
                email=email,
                role=primary.role.value,
            )

        for duplicate in matches:
            if duplicate.id == primary.id:
                continue
            if duplicate.authentik_id == authentik_id:
                duplicate.authentik_id = f"{duplicate.authentik_id}-orphan-{duplicate.id}"
            duplicate.deleted_at = datetime.now(timezone.utc)
            await self._repo.update(duplicate)
            logger.warning(
                "duplicate_user_soft_deleted",
                user_id=duplicate.id,
                email=email,
                role=duplicate.role.value,
                kept_user_id=primary.id,
            )
        return primary

    async def _reconcile_claims_onto_user(
        self,
        user: User,
        *,
        claimed_role: UserRole,
        role_claim_present: bool,
        claimed_district: str | None,
        district_claim_present: bool,
        claimed_school: str | None,
        school_claim_present: bool,
        claimed_scoped_ids: str | None,
        scoped_ids_claim_present: bool,
    ) -> User:
        """Apply JWT role/org-scope onto an existing user when claims are present."""
        changed = False
        if role_claim_present and user.role != claimed_role:
            user.role = claimed_role
            changed = True
        if district_claim_present and user.district_id != claimed_district:
            user.district_id = claimed_district
            changed = True
        if school_claim_present and user.school_id != claimed_school:
            user.school_id = claimed_school
            changed = True
        if scoped_ids_claim_present and user.scoped_ids != claimed_scoped_ids:
            user.scoped_ids = claimed_scoped_ids
            changed = True
        if not changed:
            return user
        updated = await self._repo.update(user)
        logger.info(
            "user_claims_reconciled_from_jwt",
            user_id=updated.id,
            role=updated.role.value,
            district_id=updated.district_id,
            school_id=updated.school_id,
            scoped_ids=updated.scoped_ids,
        )
        return updated

    async def get_or_create_from_jwt(self, claims: dict[str, object]) -> tuple[User, bool]:
        """Upsert a user record from JWT claims on first OIDC login.

        Returns (user, is_first_login). is_first_login=True when a new row was created.
        """
        authentik_id = str(claims.get("sub", ""))
        email = str(claims.get("email", "")).strip().lower()

        claimed_role = parse_user_role(claims.get("role", "student"))
        # Authentik is source of truth for role/scope when the `iqbalai` scope
        # mapping emits them. Reconcile on every login so a missing-scope first
        # login (defaults to student / no district) does not permanently trap
        # the user on wrong-role pages or 403 district-scoped routes.
        role_claim_present = bool(str(claims.get("role") or "").strip())
        claimed_district = str(claims.get("district_id") or "").strip() or None
        claimed_school = str(claims.get("school_id") or "").strip() or None
        claimed_scoped = str(claims.get("scoped_ids") or "").strip() or None
        district_claim_present = "district_id" in claims
        school_claim_present = "school_id" in claims
        scoped_ids_claim_present = "scoped_ids" in claims

        existing = await self._repo.get_by_authentik_id(authentik_id)
        if existing:
            return (
                await self._reconcile_claims_onto_user(
                    existing,
                    claimed_role=claimed_role,
                    role_claim_present=role_claim_present,
                    claimed_district=claimed_district,
                    district_claim_present=district_claim_present,
                    claimed_school=claimed_school,
                    school_claim_present=school_claim_present,
                    claimed_scoped_ids=claimed_scoped,
                    scoped_ids_claim_present=scoped_ids_claim_present,
                ),
                False,
            )

        if email:
            reconciled = await self._reconcile_authentik_id_by_email(
                authentik_id=authentik_id,
                email=email,
            )
            if reconciled is not None:
                return (
                    await self._reconcile_claims_onto_user(
                        reconciled,
                        claimed_role=claimed_role,
                        role_claim_present=role_claim_present,
                        claimed_district=claimed_district,
                        district_claim_present=district_claim_present,
                        claimed_school=claimed_school,
                        school_claim_present=school_claim_present,
                        claimed_scoped_ids=claimed_scoped,
                        scoped_ids_claim_present=scoped_ids_claim_present,
                    ),
                    False,
                )

        user = User(
            authentik_id=authentik_id,
            email=email,
            display_name=str(claims.get("name", claims.get("email", ""))),
            role=claimed_role,
            status=UserAccountStatus.ACTIVE,
            school_id=claimed_school,
            district_id=claimed_district,
            scoped_ids=claimed_scoped,
        )
        created = await self._repo.create(user)
        logger.info("user_created", user_id=created.id, role=created.role.value)
        return created, True

    async def get_me(self, authentik_id: str) -> User | None:
        """Return the User record for the currently authenticated user."""
        return await self._repo.get_by_authentik_id(authentik_id)

    async def suspend_for_tos_decline(self, user_id: str) -> User:
        """Mark account SUSPENDED when the user declines ToS (Flow 1 §5.6)."""
        user = await self._repo.get_by_id(user_id)
        if user is None:
            from app.core.exceptions import NotFoundError

            raise NotFoundError("User not found")
        user.status = UserAccountStatus.SUSPENDED
        return await self._repo.update(user)

    async def reactivate_on_tos_accept(self, user_id: str) -> User:
        """Restore ACTIVE when a suspended user accepts the current ToS."""
        user = await self._repo.get_by_id(user_id)
        if user is None:
            from app.core.exceptions import NotFoundError

            raise NotFoundError("User not found")
        if user.status == UserAccountStatus.SUSPENDED:
            user.status = UserAccountStatus.ACTIVE
            return await self._repo.update(user)
        return user
