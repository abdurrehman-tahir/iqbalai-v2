"""Self-study entering-mode + state persistence — T-209 (Flow 8 §3.1)."""

from __future__ import annotations

from typing import Literal, cast

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, PermissionDeniedError
from app.core.tenant import get_tenant_type
from app.features.independent_users.models import IndependentUser, IndependentUserRole
from app.features.independent_users.repository import IndependentUserRepository
from app.features.self_study.models import IndependentUserSettings
from app.features.self_study.repository import IndependentUserSettingsRepository
from app.features.self_study.schemas import (
    SelfStudyEntryRead,
    SelfStudyPersistedState,
    SelfStudyStateUpdate,
    SelfStudySubscriptionGateRead,
)
from app.features.self_study.subscription_gate import check_self_study_subscription_limits
from app.features.student_mode.models import DEFAULT_MODE_STATE, StudyMode, UserSettings
from app.features.student_mode.repository import UserSettingsRepository
from app.features.users.models import User, UserRole
from app.features.users.repository import UserRepository

logger = structlog.get_logger(__name__)

_INDEPENDENT_HOME = "/independent/student"
_SELF_STUDY_KEYS = ("last_goal_id", "last_material_id", "last_plan_view")


def _state_from_blob(raw: dict[str, object] | None) -> SelfStudyPersistedState:
    if not raw:
        return SelfStudyPersistedState()
    self_study = raw.get("self_study")
    if not isinstance(self_study, dict):
        return SelfStudyPersistedState()
    kwargs: dict[str, str | None] = {}
    for key in _SELF_STUDY_KEYS:
        val = self_study.get(key)
        kwargs[key] = str(val) if val is not None else None
    return SelfStudyPersistedState(**kwargs)


def _merge_self_study_blob(
    existing: dict[str, object],
    update: SelfStudyStateUpdate,
) -> dict[str, object]:
    self_study_raw = existing.get("self_study")
    self_study: dict[str, object] = dict(self_study_raw) if isinstance(self_study_raw, dict) else {}
    payload = update.model_dump(exclude_unset=True)
    for key, value in payload.items():
        if value is None:
            self_study.pop(key, None)
        else:
            self_study[key] = value
    out = dict(existing)
    out["self_study"] = self_study
    if "lecture" not in out:
        out["lecture"] = {}
    return out


def _gate_read() -> SelfStudySubscriptionGateRead:
    result = check_self_study_subscription_limits()
    return SelfStudySubscriptionGateRead(
        enforced=result.enforced,
        allowed=result.allowed,
        max_active_plans=result.limits.max_active_plans,
        max_monthly_uploads=result.limits.max_monthly_uploads,
    )


class SelfStudyEntryService:
    """Entering-mode behaviour for both tenant types."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._school_users = UserRepository(session)
        self._ind_users = IndependentUserRepository(session)
        self._school_settings = UserSettingsRepository(session)
        self._ind_settings = IndependentUserSettingsRepository(session)

    async def _require_school_student(self, claims: dict[str, object]) -> User:
        role = str(claims.get("role", ""))
        if role != UserRole.STUDENT.value:
            raise PermissionDeniedError("Requires a school student account")
        user = await self._school_users.get_by_authentik_id(str(claims.get("sub", "")))
        if user is None or user.role != UserRole.STUDENT:
            raise NotFoundError("Student not found")
        return user

    async def _require_independent_student(self, claims: dict[str, object]) -> IndependentUser:
        user = await self._ind_users.get_by_authentik_id(str(claims.get("sub", "")))
        if user is None or user.role != IndependentUserRole.INDEPENDENT_STUDENT:
            raise NotFoundError("Independent student not found")
        return user

    async def get_entry(self, claims: dict[str, object]) -> SelfStudyEntryRead:
        tenant = get_tenant_type(claims)
        if tenant == "independent":
            return await self._entry_independent(claims)
        return await self._entry_school(claims)

    async def _entry_school(self, claims: dict[str, object]) -> SelfStudyEntryRead:
        user = await self._require_school_student(claims)
        settings = await self._school_settings.get_by_user_id(user.id)
        if settings is None:
            settings = UserSettings(
                user_id=user.id,
                active_mode=StudyMode.SELF_STUDY,
                mode_state_jsonb=dict(DEFAULT_MODE_STATE),
            )
            settings = await self._school_settings.create(settings)
        active = cast(
            Literal["lecture", "self_study"],
            settings.active_mode.value,
        )
        return SelfStudyEntryRead(
            tenant_type="school",
            locked_to_self_study=False,
            active_mode=active,
            state=_state_from_blob(settings.mode_state_jsonb),
            subscription_gate=_gate_read(),
            lecture_mode_redirect_to=None,
        )

    async def _entry_independent(self, claims: dict[str, object]) -> SelfStudyEntryRead:
        user = await self._require_independent_student(claims)
        settings = await self._ind_settings.get_by_user_id(user.id)
        if settings is None:
            settings = IndependentUserSettings(
                user_id=user.id,
                active_mode="self_study",
                mode_state_jsonb={"self_study": {}},
            )
            settings = await self._ind_settings.create(settings)
        return SelfStudyEntryRead(
            tenant_type="independent",
            locked_to_self_study=True,
            active_mode="self_study",
            state=_state_from_blob(settings.mode_state_jsonb),
            subscription_gate=_gate_read(),
            lecture_mode_redirect_to=_INDEPENDENT_HOME,
        )

    async def update_state(
        self,
        payload: SelfStudyStateUpdate,
        claims: dict[str, object],
    ) -> SelfStudyEntryRead:
        tenant = get_tenant_type(claims)
        if tenant == "independent":
            return await self._update_independent(payload, claims)
        return await self._update_school(payload, claims)

    async def _update_school(
        self,
        payload: SelfStudyStateUpdate,
        claims: dict[str, object],
    ) -> SelfStudyEntryRead:
        user = await self._require_school_student(claims)
        settings = await self._school_settings.get_by_user_id(user.id)
        if settings is None:
            settings = UserSettings(
                user_id=user.id,
                active_mode=StudyMode.SELF_STUDY,
                mode_state_jsonb=dict(DEFAULT_MODE_STATE),
            )
            settings = await self._school_settings.create(settings)
        settings.mode_state_jsonb = _merge_self_study_blob(
            dict(settings.mode_state_jsonb),
            payload,
        )
        settings = await self._school_settings.update(settings)
        logger.info("self_study_state_updated", tenant="school", user_id=user.id)
        return SelfStudyEntryRead(
            tenant_type="school",
            locked_to_self_study=False,
            active_mode=cast(Literal["lecture", "self_study"], settings.active_mode.value),
            state=_state_from_blob(settings.mode_state_jsonb),
            subscription_gate=_gate_read(),
            lecture_mode_redirect_to=None,
        )

    async def _update_independent(
        self,
        payload: SelfStudyStateUpdate,
        claims: dict[str, object],
    ) -> SelfStudyEntryRead:
        user = await self._require_independent_student(claims)
        settings = await self._ind_settings.get_by_user_id(user.id)
        if settings is None:
            settings = IndependentUserSettings(
                user_id=user.id,
                active_mode="self_study",
                mode_state_jsonb={"self_study": {}},
            )
            settings = await self._ind_settings.create(settings)
        settings.mode_state_jsonb = _merge_self_study_blob(
            dict(settings.mode_state_jsonb),
            payload,
        )
        settings = await self._ind_settings.update(settings)
        logger.info("self_study_state_updated", tenant="independent", user_id=user.id)
        return SelfStudyEntryRead(
            tenant_type="independent",
            locked_to_self_study=True,
            active_mode="self_study",
            state=_state_from_blob(settings.mode_state_jsonb),
            subscription_gate=_gate_read(),
            lecture_mode_redirect_to=_INDEPENDENT_HOME,
        )
