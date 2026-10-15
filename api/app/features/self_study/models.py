"""Self-study ORM — T-209 (Flow 8 §3.1 / §10).

Tables live in BOTH ``school`` and ``independent`` schemas (tenant-routed).
Privacy #72 reuses ``school.user_settings.teacher_activity_share`` (T-162 /
BLOCKED-HOOK → T-220 reconcile) — no second ``student_self_study_privacy`` table.
Independent state persistence uses ``independent.user_settings`` (mode locked
to self_study; no switcher).
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base, SoftDeleteMixin, _uuid7


class SelfStudyTenantType(StrEnum):
    SCHOOL = "school"
    INDEPENDENT = "independent"


class MaterialSourceType(StrEnum):
    PDF = "pdf"
    CAMERA = "camera"
    GALLERY = "gallery"
    TYPED = "typed"


class MaterialBookType(StrEnum):
    PREP_QUESTIONS = "prep_questions"
    REFERENCE_CONTENT = "reference_content"


class StudyPlanStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class StudyPlanGranularity(StrEnum):
    DAY = "day"
    THREE_DAY = "3day"
    WEEK = "week"


def _tenant_type_enum(schema: str) -> SAEnum:
    return SAEnum(
        SelfStudyTenantType,
        name="self_study_tenant_type_enum",
        schema=schema,
        values_callable=lambda items: [item.value for item in items],
        native_enum=True,
        create_type=False,
    )


def _source_type_enum(schema: str) -> SAEnum:
    return SAEnum(
        MaterialSourceType,
        name="student_materials_source_type_enum",
        schema=schema,
        values_callable=lambda items: [item.value for item in items],
        native_enum=True,
        create_type=False,
    )


def _book_type_enum(schema: str) -> SAEnum:
    return SAEnum(
        MaterialBookType,
        name="student_materials_book_type_enum",
        schema=schema,
        values_callable=lambda items: [item.value for item in items],
        native_enum=True,
        create_type=False,
    )


def _plan_status_enum(schema: str) -> SAEnum:
    return SAEnum(
        StudyPlanStatus,
        name="study_plans_status_enum",
        schema=schema,
        values_callable=lambda items: [item.value for item in items],
        native_enum=True,
        create_type=False,
    )


def _granularity_enum(schema: str, type_name: str) -> SAEnum:
    return SAEnum(
        StudyPlanGranularity,
        name=type_name,
        schema=schema,
        values_callable=lambda items: [item.value for item in items],
        native_enum=True,
        create_type=False,
    )


# ---------------------------------------------------------------------------
# Independent user_settings — state persistence (no mode switcher)
# ---------------------------------------------------------------------------


class IndependentUserSettings(AuditMixin, SoftDeleteMixin, Base):
    """Independent-student settings — locked to self-study; persists UI state.

    School students use ``school.user_settings`` (T-101). Independent students
    have no Lecture ⇄ Self-Study toggle (Flow 8 §3.1).
    """

    __tablename__ = "user_settings"
    __table_args__ = {"schema": "independent"}

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("independent.users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    # Always ``self_study`` for independent students — column kept for parity
    # with school.user_settings so state APIs share the same shape.
    active_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="self_study")
    # {"self_study": {"last_goal_id": ..., "last_material_id": ..., "last_plan_view": ...}}
    mode_state_jsonb: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)

    def __init__(self, **kwargs: object) -> None:
        if "active_mode" not in kwargs:
            kwargs["active_mode"] = "self_study"
        if "mode_state_jsonb" not in kwargs:
            kwargs["mode_state_jsonb"] = {"self_study": {}}
        super().__init__(**kwargs)


class SchoolStudentMaterial(AuditMixin, SoftDeleteMixin, Base):
    """Personal-pool material (school schema)."""

    __tablename__ = "student_materials"
    __table_args__ = (
        Index("ix_student_materials_student_user_id", "student_user_id"),
        {"schema": "school"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    tenant_type: Mapped[SelfStudyTenantType] = mapped_column(
        _tenant_type_enum("school"),
        nullable=False,
        default=SelfStudyTenantType.SCHOOL,
    )
    student_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("school.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    source_type: Mapped[MaterialSourceType] = mapped_column(
        _source_type_enum("school"), nullable=False
    )
    book_type: Mapped[MaterialBookType | None] = mapped_column(
        _book_type_enum("school"), nullable=True
    )
    storage_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    added_to_library: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        if "tenant_type" not in kwargs:
            kwargs["tenant_type"] = SelfStudyTenantType.SCHOOL
        if "added_to_library" not in kwargs:
            kwargs["added_to_library"] = False
        super().__init__(**kwargs)


class IndependentStudentMaterial(AuditMixin, SoftDeleteMixin, Base):
    """Personal-pool material (independent schema)."""

    __tablename__ = "student_materials"
    __table_args__ = (
        Index("ix_ind_student_materials_student_user_id", "student_user_id"),
        {"schema": "independent"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    tenant_type: Mapped[SelfStudyTenantType] = mapped_column(
        _tenant_type_enum("independent"),
        nullable=False,
        default=SelfStudyTenantType.INDEPENDENT,
    )
    student_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("independent.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    source_type: Mapped[MaterialSourceType] = mapped_column(
        _source_type_enum("independent"), nullable=False
    )
    book_type: Mapped[MaterialBookType | None] = mapped_column(
        _book_type_enum("independent"), nullable=True
    )
    storage_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    added_to_library: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        if "tenant_type" not in kwargs:
            kwargs["tenant_type"] = SelfStudyTenantType.INDEPENDENT
        if "added_to_library" not in kwargs:
            kwargs["added_to_library"] = False
        super().__init__(**kwargs)


class SchoolStudentGoal(AuditMixin, Base):
    """Daily goal (#69) — school schema."""

    __tablename__ = "student_goals"
    __table_args__ = (
        UniqueConstraint(
            "student_user_id",
            "goal_date",
            name="student_goals_student_date_uq",
        ),
        Index("ix_student_goals_student_user_id", "student_user_id"),
        {"schema": "school"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    tenant_type: Mapped[SelfStudyTenantType] = mapped_column(
        _tenant_type_enum("school"),
        nullable=False,
        default=SelfStudyTenantType.SCHOOL,
    )
    student_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("school.users.id", ondelete="CASCADE"),
        nullable=False,
    )
    goal_date: Mapped[date] = mapped_column(Date, nullable=False)
    goal_text: Mapped[str] = mapped_column(Text, nullable=False)
    achieved: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    achieved_response_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        if "tenant_type" not in kwargs:
            kwargs["tenant_type"] = SelfStudyTenantType.SCHOOL
        super().__init__(**kwargs)


class IndependentStudentGoal(AuditMixin, Base):
    """Daily goal (#69) — independent schema."""

    __tablename__ = "student_goals"
    __table_args__ = (
        UniqueConstraint(
            "student_user_id",
            "goal_date",
            name="ind_student_goals_student_date_uq",
        ),
        Index("ix_ind_student_goals_student_user_id", "student_user_id"),
        {"schema": "independent"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    tenant_type: Mapped[SelfStudyTenantType] = mapped_column(
        _tenant_type_enum("independent"),
        nullable=False,
        default=SelfStudyTenantType.INDEPENDENT,
    )
    student_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("independent.users.id", ondelete="CASCADE"),
        nullable=False,
    )
    goal_date: Mapped[date] = mapped_column(Date, nullable=False)
    goal_text: Mapped[str] = mapped_column(Text, nullable=False)
    achieved: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    achieved_response_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        if "tenant_type" not in kwargs:
            kwargs["tenant_type"] = SelfStudyTenantType.INDEPENDENT
        super().__init__(**kwargs)


class SchoolPrepBookTopic(AuditMixin, Base):
    """Weighted topic extracted from a prep book (#64) — school."""

    __tablename__ = "prep_book_topics"
    __table_args__ = (
        Index("ix_prep_book_topics_student_material_id", "student_material_id"),
        {"schema": "school"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    tenant_type: Mapped[SelfStudyTenantType] = mapped_column(
        _tenant_type_enum("school"),
        nullable=False,
        default=SelfStudyTenantType.SCHOOL,
    )
    student_material_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("school.student_materials.id", ondelete="CASCADE"),
        nullable=False,
    )
    topic_label: Mapped[str] = mapped_column(String(500), nullable=False)
    # Opaque syllabus mapping UUID — no cross-schema FK (§4.21).
    curriculum_topic_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    question_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    extracted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        if "tenant_type" not in kwargs:
            kwargs["tenant_type"] = SelfStudyTenantType.SCHOOL
        if "question_count" not in kwargs:
            kwargs["question_count"] = 0
        if "weight" not in kwargs:
            kwargs["weight"] = 0.0
        super().__init__(**kwargs)


class IndependentPrepBookTopic(AuditMixin, Base):
    """Weighted topic extracted from a prep book (#64) — independent."""

    __tablename__ = "prep_book_topics"
    __table_args__ = (
        Index("ix_ind_prep_book_topics_student_material_id", "student_material_id"),
        {"schema": "independent"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    tenant_type: Mapped[SelfStudyTenantType] = mapped_column(
        _tenant_type_enum("independent"),
        nullable=False,
        default=SelfStudyTenantType.INDEPENDENT,
    )
    student_material_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("independent.student_materials.id", ondelete="CASCADE"),
        nullable=False,
    )
    topic_label: Mapped[str] = mapped_column(String(500), nullable=False)
    curriculum_topic_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    question_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    extracted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        if "tenant_type" not in kwargs:
            kwargs["tenant_type"] = SelfStudyTenantType.INDEPENDENT
        if "question_count" not in kwargs:
            kwargs["question_count"] = 0
        if "weight" not in kwargs:
            kwargs["weight"] = 0.0
        super().__init__(**kwargs)


class SchoolStudyPlan(AuditMixin, SoftDeleteMixin, Base):
    """Study plan header (#65/#66) — school."""

    __tablename__ = "study_plans"
    __table_args__ = (
        Index("ix_study_plans_student_user_id", "student_user_id"),
        {"schema": "school"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    tenant_type: Mapped[SelfStudyTenantType] = mapped_column(
        _tenant_type_enum("school"),
        nullable=False,
        default=SelfStudyTenantType.SCHOOL,
    )
    student_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("school.users.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Opaque platform exam-framework id (cross-schema view for independent).
    exam_type_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    exam_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    daily_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    strong_topics: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    status: Mapped[StudyPlanStatus] = mapped_column(
        _plan_status_enum("school"),
        nullable=False,
        default=StudyPlanStatus.ACTIVE,
    )
    granularity_current: Mapped[StudyPlanGranularity] = mapped_column(
        _granularity_enum("school", "study_plans_granularity_current_enum"),
        nullable=False,
        default=StudyPlanGranularity.DAY,
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Subscription gate hook (Flow 13 / M-23) — limits unset ⇒ no-op at launch.
    subscription_tier_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        if "tenant_type" not in kwargs:
            kwargs["tenant_type"] = SelfStudyTenantType.SCHOOL
        if "daily_hours" not in kwargs:
            kwargs["daily_hours"] = 2
        if "strong_topics" not in kwargs:
            kwargs["strong_topics"] = []
        if "status" not in kwargs:
            kwargs["status"] = StudyPlanStatus.ACTIVE
        if "granularity_current" not in kwargs:
            kwargs["granularity_current"] = StudyPlanGranularity.DAY
        super().__init__(**kwargs)


class IndependentStudyPlan(AuditMixin, SoftDeleteMixin, Base):
    """Study plan header (#65/#66) — independent."""

    __tablename__ = "study_plans"
    __table_args__ = (
        Index("ix_ind_study_plans_student_user_id", "student_user_id"),
        {"schema": "independent"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    tenant_type: Mapped[SelfStudyTenantType] = mapped_column(
        _tenant_type_enum("independent"),
        nullable=False,
        default=SelfStudyTenantType.INDEPENDENT,
    )
    student_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("independent.users.id", ondelete="CASCADE"),
        nullable=False,
    )
    exam_type_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    exam_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    daily_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    strong_topics: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    status: Mapped[StudyPlanStatus] = mapped_column(
        _plan_status_enum("independent"),
        nullable=False,
        default=StudyPlanStatus.ACTIVE,
    )
    granularity_current: Mapped[StudyPlanGranularity] = mapped_column(
        _granularity_enum("independent", "study_plans_granularity_current_enum"),
        nullable=False,
        default=StudyPlanGranularity.DAY,
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    subscription_tier_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        if "tenant_type" not in kwargs:
            kwargs["tenant_type"] = SelfStudyTenantType.INDEPENDENT
        if "daily_hours" not in kwargs:
            kwargs["daily_hours"] = 2
        if "strong_topics" not in kwargs:
            kwargs["strong_topics"] = []
        if "status" not in kwargs:
            kwargs["status"] = StudyPlanStatus.ACTIVE
        if "granularity_current" not in kwargs:
            kwargs["granularity_current"] = StudyPlanGranularity.DAY
        super().__init__(**kwargs)


class SchoolStudyPlanItem(AuditMixin, Base):
    """Plan item at a granularity (#66) — school."""

    __tablename__ = "study_plan_items"
    __table_args__ = (
        Index("ix_study_plan_items_study_plan_id", "study_plan_id"),
        {"schema": "school"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    study_plan_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("school.study_plans.id", ondelete="CASCADE"),
        nullable=False,
    )
    granularity: Mapped[StudyPlanGranularity] = mapped_column(
        _granularity_enum("school", "study_plan_items_granularity_enum"),
        nullable=False,
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    tasks_jsonb: Mapped[list[object]] = mapped_column(JSONB, nullable=False, default=list)
    est_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    subject_color: Mapped[str] = mapped_column(String(32), nullable=False, default="")

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        if "tasks_jsonb" not in kwargs:
            kwargs["tasks_jsonb"] = []
        if "est_minutes" not in kwargs:
            kwargs["est_minutes"] = 0
        if "subject_color" not in kwargs:
            kwargs["subject_color"] = ""
        super().__init__(**kwargs)


class IndependentStudyPlanItem(AuditMixin, Base):
    """Plan item at a granularity (#66) — independent."""

    __tablename__ = "study_plan_items"
    __table_args__ = (
        Index("ix_ind_study_plan_items_study_plan_id", "study_plan_id"),
        {"schema": "independent"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    study_plan_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("independent.study_plans.id", ondelete="CASCADE"),
        nullable=False,
    )
    granularity: Mapped[StudyPlanGranularity] = mapped_column(
        _granularity_enum("independent", "study_plan_items_granularity_enum"),
        nullable=False,
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    tasks_jsonb: Mapped[list[object]] = mapped_column(JSONB, nullable=False, default=list)
    est_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    subject_color: Mapped[str] = mapped_column(String(32), nullable=False, default="")

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        if "tasks_jsonb" not in kwargs:
            kwargs["tasks_jsonb"] = []
        if "est_minutes" not in kwargs:
            kwargs["est_minutes"] = 0
        if "subject_color" not in kwargs:
            kwargs["subject_color"] = ""
        super().__init__(**kwargs)


class SchoolStudyPlanDay(AuditMixin, Base):
    """Adherence day row (#70) — school."""

    __tablename__ = "study_plan_days"
    __table_args__ = (
        UniqueConstraint(
            "study_plan_id",
            "day_date",
            name="study_plan_days_plan_date_uq",
        ),
        Index("ix_study_plan_days_study_plan_id", "study_plan_id"),
        {"schema": "school"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    study_plan_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("school.study_plans.id", ondelete="CASCADE"),
        nullable=False,
    )
    day_date: Mapped[date] = mapped_column(Date, nullable=False)
    scheduled_tasks_jsonb: Mapped[list[object]] = mapped_column(JSONB, nullable=False, default=list)
    completed_tasks_jsonb: Mapped[list[object]] = mapped_column(JSONB, nullable=False, default=list)
    adherence_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    consecutive_miss_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    alerted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        if "scheduled_tasks_jsonb" not in kwargs:
            kwargs["scheduled_tasks_jsonb"] = []
        if "completed_tasks_jsonb" not in kwargs:
            kwargs["completed_tasks_jsonb"] = []
        if "adherence_pct" not in kwargs:
            kwargs["adherence_pct"] = 0.0
        if "consecutive_miss_count" not in kwargs:
            kwargs["consecutive_miss_count"] = 0
        super().__init__(**kwargs)


class IndependentStudyPlanDay(AuditMixin, Base):
    """Adherence day row (#70) — independent."""

    __tablename__ = "study_plan_days"
    __table_args__ = (
        UniqueConstraint(
            "study_plan_id",
            "day_date",
            name="ind_study_plan_days_plan_date_uq",
        ),
        Index("ix_ind_study_plan_days_study_plan_id", "study_plan_id"),
        {"schema": "independent"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    study_plan_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("independent.study_plans.id", ondelete="CASCADE"),
        nullable=False,
    )
    day_date: Mapped[date] = mapped_column(Date, nullable=False)
    scheduled_tasks_jsonb: Mapped[list[object]] = mapped_column(JSONB, nullable=False, default=list)
    completed_tasks_jsonb: Mapped[list[object]] = mapped_column(JSONB, nullable=False, default=list)
    adherence_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    consecutive_miss_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    alerted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        if "scheduled_tasks_jsonb" not in kwargs:
            kwargs["scheduled_tasks_jsonb"] = []
        if "completed_tasks_jsonb" not in kwargs:
            kwargs["completed_tasks_jsonb"] = []
        if "adherence_pct" not in kwargs:
            kwargs["adherence_pct"] = 0.0
        if "consecutive_miss_count" not in kwargs:
            kwargs["consecutive_miss_count"] = 0
        super().__init__(**kwargs)


class SchoolReminderPreference(AuditMixin, Base):
    """Reminder channel prefs (#68) — school."""

    __tablename__ = "reminder_preferences"
    __table_args__ = {"schema": "school"}

    student_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("school.users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    push_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    email_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sms_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Asia/Karachi")

    def __init__(self, **kwargs: object) -> None:
        if "push_enabled" not in kwargs:
            kwargs["push_enabled"] = True
        if "email_enabled" not in kwargs:
            kwargs["email_enabled"] = True
        if "sms_enabled" not in kwargs:
            kwargs["sms_enabled"] = False
        if "timezone" not in kwargs:
            kwargs["timezone"] = "Asia/Karachi"
        super().__init__(**kwargs)


class IndependentReminderPreference(AuditMixin, Base):
    """Reminder channel prefs (#68) — independent."""

    __tablename__ = "reminder_preferences"
    __table_args__ = {"schema": "independent"}

    student_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("independent.users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    push_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    email_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sms_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Asia/Karachi")

    def __init__(self, **kwargs: object) -> None:
        if "push_enabled" not in kwargs:
            kwargs["push_enabled"] = True
        if "email_enabled" not in kwargs:
            kwargs["email_enabled"] = True
        if "sms_enabled" not in kwargs:
            kwargs["sms_enabled"] = False
        if "timezone" not in kwargs:
            kwargs["timezone"] = "Asia/Karachi"
        super().__init__(**kwargs)


# Compatibility aliases (docs / future repos default to school).
StudentMaterial = SchoolStudentMaterial
StudentGoal = SchoolStudentGoal
PrepBookTopic = SchoolPrepBookTopic
StudyPlan = SchoolStudyPlan
StudyPlanItem = SchoolStudyPlanItem
StudyPlanDay = SchoolStudyPlanDay
ReminderPreference = SchoolReminderPreference
