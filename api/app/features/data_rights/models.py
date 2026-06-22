"""DataRightsRequest ORM model — T-084 / Flow 4 §3.8."""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base, SoftDeleteMixin, _uuid7


class DataRightsRequestType(str, enum.Enum):
    EXPORT = "export"
    DELETION = "deletion"


class DataRightsRequestStatus(str, enum.Enum):
    REQUESTED = "requested"
    PROCESSING = "processing"
    READY = "ready"
    EXPIRED = "expired"
    GRACE_PERIOD = "grace_period"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class DataRightsRequest(AuditMixin, SoftDeleteMixin, Base):
    """Export or deletion request for a user's own data (PDPB §15)."""

    __tablename__ = "data_rights_requests"
    __table_args__ = {"schema": "school"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("school.users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    request_type: Mapped[DataRightsRequestType] = mapped_column(
        SAEnum(
            DataRightsRequestType,
            name="data_rights_request_type",
            schema="school",
            values_callable=lambda items: [item.value for item in items],
            native_enum=True,
            create_type=False,
        ),
        nullable=False,
    )
    status: Mapped[DataRightsRequestStatus] = mapped_column(
        SAEnum(
            DataRightsRequestStatus,
            name="data_rights_request_status",
            schema="school",
            values_callable=lambda items: [item.value for item in items],
            native_enum=True,
            create_type=False,
        ),
        nullable=False,
        index=True,
    )
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ready_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    deletion_scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    file_key: Mapped[str | None] = mapped_column(String(512), nullable=True, default=None)

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        super().__init__(**kwargs)
