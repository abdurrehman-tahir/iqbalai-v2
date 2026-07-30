"""School student mode settings ORM — T-101 (Mode Switcher).

Persists active Lecture ⇄ Self-Study mode and per-mode UI state so switches
are instant and lossless (flow-4 §3.4). Independent students have no row and
no switcher API (404).
"""

from __future__ import annotations

from enum import StrEnum

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base, SoftDeleteMixin


class StudyMode(StrEnum):
    """Active study mode for a school student (flow-4 §3.4)."""

    LECTURE = "lecture"
    SELF_STUDY = "self_study"


# Empty per-mode state blobs — Self-Study / Lecture surfaces fill these later (M-09 / M-17).
DEFAULT_MODE_STATE: dict[str, dict[str, object]] = {
    "lecture": {},
    "self_study": {},
}


class UserSettings(AuditMixin, SoftDeleteMixin, Base):
    """Per-user settings for school students — active mode + mode-state JSONB."""

    __tablename__ = "user_settings"
    __table_args__ = {"schema": "school"}

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("school.users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    active_mode: Mapped[StudyMode] = mapped_column(
        SAEnum(
            StudyMode,
            name="user_settings_active_mode_enum",
            schema="school",
            values_callable=lambda items: [item.value for item in items],
            native_enum=True,
            create_type=False,
        ),
        nullable=False,
    )
    # Per-mode restore blob: {"lecture": {...}, "self_study": {...}} — validated on write.
    mode_state_jsonb: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
    )

    def __init__(self, **kwargs: object) -> None:
        if "mode_state_jsonb" not in kwargs:
            kwargs["mode_state_jsonb"] = dict(DEFAULT_MODE_STATE)
        super().__init__(**kwargs)
