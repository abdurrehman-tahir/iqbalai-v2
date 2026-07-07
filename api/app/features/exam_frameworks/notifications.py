"""Framework notification fan-out — resolves recipients + fires per-event notices (T-097).

Kept out of the service so lifecycle methods stay lean and testable. Every helper is
best-effort: it runs *after* the lifecycle transition has committed, so a notification
failure is logged and swallowed rather than rolling back an approval/publish. Recipients
are resolved to their Authentik ``sub`` (the notification ``recipient_user_id``): Platform
Admins for research/approval alerts, and students pinned to an older version for the
``framework.version_available`` notice.
"""

from __future__ import annotations

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.exam_frameworks.models import ExamFramework, SelectionTenantType
from app.features.exam_frameworks.student_repository import StudentFrameworkRepository
from app.features.independent_users.repository import IndependentUserRepository
from app.features.users.repository import UserRepository
from app.infrastructure.notifications.framework import notify_framework_event
from app.infrastructure.notifications.templates.framework import DEFAULT_LOCALE

logger = structlog.get_logger(__name__)


async def notify_platform_admins(
    session: AsyncSession,
    *,
    template_key: str,
    framework: ExamFramework,
    extra_params: dict[str, str] | None = None,
) -> None:
    """Notify every active Platform Admin (research-complete / SLA reminder / escalation)."""
    try:
        admins = await UserRepository(session).list_platform_admins()
        params = {"framework_name": framework.name, **(extra_params or {})}
        for admin in admins:
            await notify_framework_event(
                session=session,
                template_key=template_key,
                recipient_user_id=admin.authentik_id,
                locale=DEFAULT_LOCALE,
                metadata={"framework_id": framework.id},
                params=params,
            )
    except Exception as exc:  # best-effort: never break the lifecycle transition
        logger.warning(
            "framework_admin_notify_failed",
            template_key=template_key,
            framework_id=framework.id,
            error=str(exc),
        )


async def notify_version_available(
    session: AsyncSession,
    *,
    framework: ExamFramework,
    new_version: int,
) -> None:
    """Notify students pinned to an older version that a refreshed plan is available.

    Never auto-switches (opt-in, §3.5.3) — this only surfaces the "v{n} available" notice
    each such student can act on from their framework page (T-096).
    """
    try:
        repo = StudentFrameworkRepository(session)
        users = UserRepository(session)
        independents = IndependentUserRepository(session)
        selections = await repo.list_active_selections_pinned_below(framework.id, new_version)
        params = {"framework_name": framework.name, "version": str(new_version)}
        for sel in selections:
            # student_user_id is the app user id; the notification recipient is the
            # Authentik sub, so resolve it per tenant (and use the student's locale).
            if sel.tenant_type == SelectionTenantType.INDEPENDENT:
                ind = await independents.get_by_id(sel.student_user_id)
                if ind is None:
                    continue
                recipient, locale = ind.authentik_id, ind.language_preference
            else:
                user = await users.get_by_id(sel.student_user_id)
                if user is None:
                    continue
                recipient, locale = user.authentik_id, DEFAULT_LOCALE
            await notify_framework_event(
                session=session,
                template_key="self_study.framework_version_available",
                recipient_user_id=recipient,
                locale=locale,
                metadata={"framework_id": framework.id, "version": new_version},
                params=params,
            )
    except Exception as exc:  # best-effort
        logger.warning(
            "framework_version_notify_failed",
            framework_id=framework.id,
            new_version=new_version,
            error=str(exc),
        )
