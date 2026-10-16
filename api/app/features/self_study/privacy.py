"""Self-study privacy #72 — T-220 canonical owner (Flow 8).

Storage + enforcement live on ``school.user_settings.teacher_activity_share``
(T-162). Flow 8 owns the setting's meaning for self-study: default Yes (share),
INVIOLATE when No, hidden for independent students, aggregate-anonymous signals
always flow. Mid-session toggles re-stamp subsequent events via
``current_teacher_share_stamp``.
"""

from __future__ import annotations

from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant import get_tenant_type
from app.features.student_privacy.service import student_allows_teacher_share

TeacherShareStamp = Literal["share", "private"]


async def current_teacher_share_stamp(
    session: AsyncSession,
    claims: dict[str, object],
    *,
    student_user_id: str,
) -> TeacherShareStamp | None:
    """Return #72 stamp for school students; ``None`` for independent (setting hidden)."""
    if get_tenant_type(claims) == "independent":
        return None
    allows = await student_allows_teacher_share(session, student_user_id)
    return "share" if allows else "private"


def privacy_visible_for_tenant(tenant_type: str) -> bool:
    """#72 UI exists only for school students (Flow 8 §3.12 / §3.13)."""
    return tenant_type == "school"
