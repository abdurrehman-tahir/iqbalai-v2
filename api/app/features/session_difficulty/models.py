"""session_difficulty_log — per-(session, sub_topic) adaptation signal (T-175)."""

from __future__ import annotations

from enum import StrEnum

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base, _uuid7


class DifficultyTenantType(StrEnum):
    SCHOOL = "school"
    INDEPENDENT = "independent"


def _tenant_type_enum(schema: str) -> SAEnum:
    return SAEnum(
        DifficultyTenantType,
        name="session_difficulty_log_tenant_type_enum",
        schema=schema,
        values_callable=lambda items: [item.value for item in items],
        native_enum=True,
        create_type=False,
    )


class SchoolSessionDifficultyLog(AuditMixin, Base):
    """Per-session sub-topic question counts + tried teaching angles (school)."""

    __tablename__ = "session_difficulty_log"
    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "sub_topic_id",
            name="session_difficulty_log_session_subtopic_uq",
        ),
        Index("ix_session_difficulty_log_session_id", "session_id"),
        Index("ix_session_difficulty_log_sub_topic_id", "sub_topic_id"),
        {"schema": "school"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("school.lecture_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    sub_topic_id: Mapped[str] = mapped_column(String(128), nullable=False)
    question_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tried_angles: Mapped[list[object]] = mapped_column(JSONB, nullable=False, default=list)
    last_angle: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tenant_type: Mapped[DifficultyTenantType] = mapped_column(
        _tenant_type_enum("school"),
        nullable=False,
        default=DifficultyTenantType.SCHOOL,
    )

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        if "question_count" not in kwargs:
            kwargs["question_count"] = 0
        if "tried_angles" not in kwargs:
            kwargs["tried_angles"] = []
        if "tenant_type" not in kwargs:
            kwargs["tenant_type"] = DifficultyTenantType.SCHOOL
        super().__init__(**kwargs)


class IndependentSessionDifficultyLog(AuditMixin, Base):
    """Per-session sub-topic difficulty log (independent schema).

    No FK to school lecture_sessions — independent sessions are Flow 8
    ``self_study_sessions``; ``session_id`` is an opaque UUID string.
    """

    __tablename__ = "session_difficulty_log"
    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "sub_topic_id",
            name="ind_session_difficulty_log_session_subtopic_uq",
        ),
        Index("ix_ind_session_difficulty_log_session_id", "session_id"),
        Index("ix_ind_session_difficulty_log_sub_topic_id", "sub_topic_id"),
        {"schema": "independent"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    session_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    sub_topic_id: Mapped[str] = mapped_column(String(128), nullable=False)
    question_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tried_angles: Mapped[list[object]] = mapped_column(JSONB, nullable=False, default=list)
    last_angle: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tenant_type: Mapped[DifficultyTenantType] = mapped_column(
        _tenant_type_enum("independent"),
        nullable=False,
        default=DifficultyTenantType.INDEPENDENT,
    )

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        if "question_count" not in kwargs:
            kwargs["question_count"] = 0
        if "tried_angles" not in kwargs:
            kwargs["tried_angles"] = []
        if "tenant_type" not in kwargs:
            kwargs["tenant_type"] = DifficultyTenantType.INDEPENDENT
        super().__init__(**kwargs)
