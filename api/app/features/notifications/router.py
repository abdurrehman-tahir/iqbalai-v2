"""Notifications router — bell endpoint for the current user (T-023).

Per ARCH §9.21: users see only their own notifications.
RLS at the DB layer provides an additional tenant-isolation backstop.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import NotFoundError
from app.features.notifications.repository import NotificationRepository
from app.features.notifications.schemas import NotificationListResponse, NotificationRead

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get(
    "/",
    response_model=NotificationListResponse,
    operation_id="list_notifications",
    summary="List notifications for the current user",
    description="Returns non-deleted notifications newest-first, with unread count for bell badge.",
)
async def list_notifications(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationListResponse:
    """Fetch paginated notifications + unread count for the authenticated user."""
    user_id = str(claims["sub"])
    repo = NotificationRepository(db)

    notifications = await repo.list_for_user(user_id, limit=limit, offset=offset)
    unread_count = await repo.count_unread(user_id)

    logger.info(
        "notifications_listed",
        user_id=user_id,
        count=len(notifications),
        unread=unread_count,
    )

    return NotificationListResponse(
        items=[NotificationRead.model_validate(n) for n in notifications],
        total=len(notifications),
        unread_count=unread_count,
    )


@router.post(
    "/{notif_id}/read",
    response_model=NotificationRead,
    operation_id="mark_notification_read",
    summary="Mark a notification as read",
    description="The authenticated user may only mark their own notifications as read.",
)
async def mark_notification_read(
    notif_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationRead:
    """Mark a single notification as read.

    Raises NotFoundError if the notification does not exist or belongs to another user.
    Ownership check is intentionally opaque (same 404) to avoid enumeration.
    """
    user_id = str(claims["sub"])
    repo = NotificationRepository(db)

    notif = await repo.get_by_id(notif_id)
    # Treat missing or wrong-owner as 404 to prevent notification-ID enumeration
    if notif is None or notif.recipient_user_id != user_id:
        raise NotFoundError("Notification not found")

    updated = await repo.mark_read(notif)

    logger.info("notification_marked_read", notif_id=notif_id, user_id=user_id)

    return NotificationRead.model_validate(updated)
