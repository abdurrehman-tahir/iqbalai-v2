"""Lecture ORM models — T-113 (Flow 5 §3.1–§3.2, ARCH §4.18 / §4.21).

Four tables in both ``school`` and ``independent`` schemas:
``lectures``, ``lecture_versions``, ``lecture_drafts``, ``lecture_paragraphs``.

``lecture_type`` + ``parent_lecture_id`` are Flow-7-ready (mini-lectures later).
Scoring columns stay nullable until M-10; quiz tables are M-11.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base, SoftDeleteMixin, _uuid7


class LectureType(StrEnum):
    """main = class lecture; mini = Flow-7 targeted follow-up (column reserved now)."""

    MAIN = "main"
    MINI = "mini"


class LectureStatus(StrEnum):
    """Lecture lifecycle (Flow 5 §3.1–§3.2). Additive-only per ARCH §4.9.

    M-09 ends at READY_FOR_EDIT. READY_FOR_PUBLISH / PUBLISHED / ARCHIVED are
    reserved for M-10/M-11 so later tickets do not need ALTER TYPE ADD VALUE.
    """

    DRAFT = "draft"
    GENERATING = "generating"
    GENERATED_V1 = "generated_v1"
    READY_FOR_EDIT = "ready_for_edit"
    READY_FOR_PUBLISH = "ready_for_publish"
    PUBLISHED = "published"
    ARCHIVED = "archived"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


class LectureTenantType(StrEnum):
    SCHOOL = "school"
    INDEPENDENT = "independent"


def _lecture_type_enum(schema: str) -> SAEnum:
    return SAEnum(
        LectureType,
        name="lectures_lecture_type_enum",
        schema=schema,
        values_callable=lambda items: [item.value for item in items],
        native_enum=True,
        create_type=False,
    )


def _lecture_status_enum(schema: str) -> SAEnum:
    return SAEnum(
        LectureStatus,
        name="lectures_status_enum",
        schema=schema,
        values_callable=lambda items: [item.value for item in items],
        native_enum=True,
        create_type=False,
    )


def _tenant_type_enum(schema: str) -> SAEnum:
    return SAEnum(
        LectureTenantType,
        name="lectures_tenant_type_enum",
        schema=schema,
        values_callable=lambda items: [item.value for item in items],
        native_enum=True,
        create_type=False,
    )


class VoiceSessionStatus(StrEnum):
    """ "Talk to AI" voice session lifecycle (T-121, Flow 5 §3.4 / #25)."""

    ACTIVE = "active"
    ENDED = "ended"


def _voice_session_status_enum(schema: str) -> SAEnum:
    return SAEnum(
        VoiceSessionStatus,
        name="lecture_voice_sessions_status_enum",
        schema=schema,
        values_callable=lambda items: [item.value for item in items],
        native_enum=True,
        create_type=False,
    )


class LectureAssignmentScope(StrEnum):
    """What a lecture_assignments row restricts access to (T-123, #21)."""

    STUDENT = "student"
    SECTION = "section"


def _lecture_assignment_scope_enum(schema: str) -> SAEnum:
    return SAEnum(
        LectureAssignmentScope,
        name="lecture_assignments_scope_enum",
        schema=schema,
        values_callable=lambda items: [item.value for item in items],
        native_enum=True,
        create_type=False,
    )


# ---------------------------------------------------------------------------
# School schema
# ---------------------------------------------------------------------------


class SchoolLecture(AuditMixin, SoftDeleteMixin, Base):
    """Canonical lecture identity (mutable status / current_version pointer)."""

    __tablename__ = "lectures"
    __table_args__ = (
        CheckConstraint(
            "lecture_type <> 'mini' OR parent_lecture_id IS NOT NULL",
            name="lectures_mini_requires_parent_check",
        ),
        Index("ix_lectures_school_id", "school_id"),
        Index("ix_lectures_grade_subject_offering_id", "grade_subject_offering_id"),
        Index("ix_lectures_teacher_user_id", "teacher_user_id"),
        Index("ix_lectures_parent_lecture_id", "parent_lecture_id"),
        Index("ix_lectures_current_version_id", "current_version_id"),
        {"schema": "school"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    tenant_type: Mapped[LectureTenantType] = mapped_column(
        _tenant_type_enum("school"),
        nullable=False,
        default=LectureTenantType.SCHOOL,
    )
    school_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("school.schools.id", ondelete="RESTRICT"),
        nullable=True,
    )
    grade_subject_offering_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("school.grade_subject_offerings.id", ondelete="RESTRICT"),
        nullable=True,
    )
    # SET NULL: preserve content if the teacher user is hard-removed (ARCH §4.6).
    teacher_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("school.users.id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    topic: Mapped[str] = mapped_column(String(500), nullable=False)
    lecture_type: Mapped[LectureType] = mapped_column(
        _lecture_type_enum("school"),
        nullable=False,
        default=LectureType.MAIN,
    )
    parent_lecture_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("school.lectures.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[LectureStatus] = mapped_column(
        _lecture_status_enum("school"),
        nullable=False,
        default=LectureStatus.DRAFT,
    )
    # Circular with lecture_versions — FK added via use_alter after versions exist (§4.18).
    current_version_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey(
            "school.lecture_versions.id",
            ondelete="RESTRICT",
            use_alter=True,
            name="lectures_current_version_id_fk",
        ),
        nullable=True,
    )

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        if "tenant_type" not in kwargs:
            kwargs["tenant_type"] = LectureTenantType.SCHOOL
        if "lecture_type" not in kwargs:
            kwargs["lecture_type"] = LectureType.MAIN
        if "status" not in kwargs:
            kwargs["status"] = LectureStatus.DRAFT
        super().__init__(**kwargs)


class SchoolLectureVersion(AuditMixin, Base):
    """Immutable append-only version row (§4.18). No soft-delete."""

    __tablename__ = "lecture_versions"
    __table_args__ = (
        UniqueConstraint(
            "lecture_id",
            "version",
            name="lecture_versions_lecture_version_uq",
        ),
        CheckConstraint("version >= 1", name="lecture_versions_version_positive_check"),
        {"schema": "school"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    lecture_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("school.lectures.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    # M-10 fills 7-dimension scores; nullable until then.
    scores_jsonb: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        super().__init__(**kwargs)


class SchoolLectureParagraph(AuditMixin, Base):
    """Per-paragraph body + provenance for a lecture version."""

    __tablename__ = "lecture_paragraphs"
    __table_args__ = (
        UniqueConstraint(
            "lecture_version_id",
            "ordinal",
            name="lecture_paragraphs_version_ordinal_uq",
        ),
        CheckConstraint("ordinal >= 0", name="lecture_paragraphs_ordinal_nonneg_check"),
        {"schema": "school"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    lecture_version_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("school.lecture_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    source_metadata_jsonb: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        if "source_metadata_jsonb" not in kwargs:
            kwargs["source_metadata_jsonb"] = {"tier": "ai_knowledge"}
        super().__init__(**kwargs)


class SchoolLectureVoiceSession(AuditMixin, Base):
    """A "Talk to AI" voice session (T-121, #25). No soft-delete — sessions end,
    they aren't deleted; ``created_at`` (AuditMixin) doubles as ``started_at``.
    """

    __tablename__ = "lecture_voice_sessions"
    __table_args__ = (
        Index("ix_lecture_voice_sessions_lecture_id", "lecture_id"),
        Index("ix_lecture_voice_sessions_teacher_user_id", "teacher_user_id"),
        {"schema": "school"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    lecture_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("school.lectures.id", ondelete="CASCADE"),
        nullable=False,
    )
    teacher_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("school.users.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[VoiceSessionStatus] = mapped_column(
        _voice_session_status_enum("school"),
        nullable=False,
        default=VoiceSessionStatus.ACTIVE,
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        if "status" not in kwargs:
            kwargs["status"] = VoiceSessionStatus.ACTIVE
        super().__init__(**kwargs)


class SchoolLectureVoiceTurn(AuditMixin, Base):
    """Append-only per-turn record: transcript + edit + audio pointer (§4.18 pattern)."""

    __tablename__ = "lecture_voice_turns"
    __table_args__ = (
        UniqueConstraint("session_id", "ordinal", name="lecture_voice_turns_session_ordinal_uq"),
        CheckConstraint("ordinal >= 0", name="lecture_voice_turns_ordinal_nonneg_check"),
        Index("ix_lecture_voice_turns_session_id", "session_id"),
        {"schema": "school"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("school.lecture_voice_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    # What the teacher said (faster-whisper STT output).
    transcript: Mapped[str] = mapped_column(Text, nullable=False)
    # Echo/confirmation/answer spoken back via TTS (flow-5 §5.4 "Did you mean: ...").
    ai_response_text: Mapped[str] = mapped_column(Text, nullable=False)
    # VoiceEditOperation JSONB, or null when the turn made no draft change.
    edit_operation_jsonb: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    # MinIO key (audio bucket) for the raw turn audio; null once purged.
    audio_storage_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    audio_purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        super().__init__(**kwargs)


class SchoolLectureDraft(AuditMixin, SoftDeleteMixin, Base):
    """Wizard auto-save blob — one active draft per teacher (T-114 resume)."""

    __tablename__ = "lecture_drafts"
    __table_args__ = (
        Index(
            "lecture_drafts_teacher_user_id_uq",
            "teacher_user_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        {"schema": "school"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    teacher_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("school.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    wizard_state_jsonb: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        if "wizard_state_jsonb" not in kwargs:
            kwargs["wizard_state_jsonb"] = {"step": 1, "data": {}}
        super().__init__(**kwargs)


class SchoolLectureLink(AuditMixin, Base):
    """Links a lecture into an additional Grade-Subject offering (T-122, #21).

    Self-link only: the teacher links one of their own lectures into another
    Grade-Subject offering they're assigned to (auto-approve, no admin-approval
    workflow — narrower than flow-5 §3.13's full cross-teacher lifecycle, per
    this ticket's acceptance criteria). No soft-delete: a link either exists
    or is removed outright. School schema only — independent lectures have no
    Grade-Subject offering to link into (ARCH §3.18).
    """

    __tablename__ = "lecture_links"
    __table_args__ = (
        UniqueConstraint(
            "lecture_id",
            "target_grade_subject_offering_id",
            name="lecture_links_lecture_target_uq",
        ),
        Index("ix_lecture_links_lecture_id", "lecture_id"),
        Index(
            "ix_lecture_links_target_grade_subject_offering_id",
            "target_grade_subject_offering_id",
        ),
        {"schema": "school"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    lecture_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("school.lectures.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_grade_subject_offering_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("school.grade_subject_offerings.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_by_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("school.users.id", ondelete="SET NULL"),
        nullable=True,
    )

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        super().__init__(**kwargs)


class SchoolLectureAssignment(AuditMixin, Base):
    """Restricts a lecture's default visibility to specific students/sections (T-123, #21).

    Default (no rows for a lecture): visible to every student actively enrolled
    in the lecture's Grade-Subject offering's grade. One or more rows: visible
    only to students matched by a row (directly by ``student_user_id``, or via
    their section's ``section_id``). "Group" targeting (Flow 11) is out of
    scope — that model doesn't exist yet in this codebase. No soft-delete: a
    restriction either exists or is removed outright (replace-all semantics).
    """

    __tablename__ = "lecture_assignments"
    __table_args__ = (
        CheckConstraint(
            "(scope = 'student' AND student_user_id IS NOT NULL AND section_id IS NULL) OR "
            "(scope = 'section' AND section_id IS NOT NULL AND student_user_id IS NULL)",
            name="lecture_assignments_scope_target_check",
        ),
        UniqueConstraint(
            "lecture_id", "student_user_id", name="lecture_assignments_lecture_student_uq"
        ),
        UniqueConstraint("lecture_id", "section_id", name="lecture_assignments_lecture_section_uq"),
        Index("ix_lecture_assignments_lecture_id", "lecture_id"),
        {"schema": "school"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    lecture_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("school.lectures.id", ondelete="CASCADE"),
        nullable=False,
    )
    scope: Mapped[LectureAssignmentScope] = mapped_column(
        _lecture_assignment_scope_enum("school"),
        nullable=False,
    )
    # A row referencing a deleted student/section no longer means anything — cascade it away.
    student_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("school.users.id", ondelete="CASCADE"),
        nullable=True,
    )
    section_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("school.sections.id", ondelete="CASCADE"),
        nullable=True,
    )
    created_by_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("school.users.id", ondelete="SET NULL"),
        nullable=True,
    )

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        super().__init__(**kwargs)


# ---------------------------------------------------------------------------
# Independent schema — same tables; school_id / offering_id always null (no FKs).
# ---------------------------------------------------------------------------


class IndependentLecture(AuditMixin, SoftDeleteMixin, Base):
    """Independent-teacher lecture — no Grade-Subject offering, no school_id."""

    __tablename__ = "lectures"
    __table_args__ = (
        CheckConstraint(
            "lecture_type <> 'mini' OR parent_lecture_id IS NOT NULL",
            name="lectures_mini_requires_parent_check",
        ),
        CheckConstraint("school_id IS NULL", name="lectures_independent_school_null_check"),
        CheckConstraint(
            "grade_subject_offering_id IS NULL",
            name="lectures_independent_offering_null_check",
        ),
        Index("ix_lectures_teacher_user_id", "teacher_user_id"),
        Index("ix_lectures_parent_lecture_id", "parent_lecture_id"),
        Index("ix_lectures_current_version_id", "current_version_id"),
        {"schema": "independent"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    tenant_type: Mapped[LectureTenantType] = mapped_column(
        _tenant_type_enum("independent"),
        nullable=False,
        default=LectureTenantType.INDEPENDENT,
    )
    # Always NULL for independent — columns exist for shape parity; no cross-schema FKs.
    school_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    grade_subject_offering_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    teacher_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("independent.users.id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    topic: Mapped[str] = mapped_column(String(500), nullable=False)
    lecture_type: Mapped[LectureType] = mapped_column(
        _lecture_type_enum("independent"),
        nullable=False,
        default=LectureType.MAIN,
    )
    parent_lecture_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("independent.lectures.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[LectureStatus] = mapped_column(
        _lecture_status_enum("independent"),
        nullable=False,
        default=LectureStatus.DRAFT,
    )
    current_version_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey(
            "independent.lecture_versions.id",
            ondelete="RESTRICT",
            use_alter=True,
            name="lectures_current_version_id_fk",
        ),
        nullable=True,
    )

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        if "tenant_type" not in kwargs:
            kwargs["tenant_type"] = LectureTenantType.INDEPENDENT
        if "lecture_type" not in kwargs:
            kwargs["lecture_type"] = LectureType.MAIN
        if "status" not in kwargs:
            kwargs["status"] = LectureStatus.DRAFT
        # Enforce independent nullability even if callers pass values.
        kwargs["school_id"] = None
        kwargs["grade_subject_offering_id"] = None
        super().__init__(**kwargs)


class IndependentLectureVersion(AuditMixin, Base):
    """Immutable append-only version in the independent schema."""

    __tablename__ = "lecture_versions"
    __table_args__ = (
        UniqueConstraint(
            "lecture_id",
            "version",
            name="lecture_versions_lecture_version_uq",
        ),
        CheckConstraint("version >= 1", name="lecture_versions_version_positive_check"),
        {"schema": "independent"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    lecture_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("independent.lectures.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    scores_jsonb: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        super().__init__(**kwargs)


class IndependentLectureParagraph(AuditMixin, Base):
    """Per-paragraph body + provenance (independent schema)."""

    __tablename__ = "lecture_paragraphs"
    __table_args__ = (
        UniqueConstraint(
            "lecture_version_id",
            "ordinal",
            name="lecture_paragraphs_version_ordinal_uq",
        ),
        CheckConstraint("ordinal >= 0", name="lecture_paragraphs_ordinal_nonneg_check"),
        {"schema": "independent"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    lecture_version_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("independent.lecture_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    source_metadata_jsonb: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        if "source_metadata_jsonb" not in kwargs:
            kwargs["source_metadata_jsonb"] = {"tier": "ai_knowledge"}
        super().__init__(**kwargs)


class IndependentLectureVoiceSession(AuditMixin, Base):
    """Voice session, independent schema (T-121 acceptance #5)."""

    __tablename__ = "lecture_voice_sessions"
    __table_args__ = (
        Index("ix_lecture_voice_sessions_lecture_id", "lecture_id"),
        Index("ix_lecture_voice_sessions_teacher_user_id", "teacher_user_id"),
        {"schema": "independent"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    lecture_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("independent.lectures.id", ondelete="CASCADE"),
        nullable=False,
    )
    teacher_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("independent.users.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[VoiceSessionStatus] = mapped_column(
        _voice_session_status_enum("independent"),
        nullable=False,
        default=VoiceSessionStatus.ACTIVE,
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        if "status" not in kwargs:
            kwargs["status"] = VoiceSessionStatus.ACTIVE
        super().__init__(**kwargs)


class IndependentLectureVoiceTurn(AuditMixin, Base):
    """Voice turn, independent schema (T-121 acceptance #5)."""

    __tablename__ = "lecture_voice_turns"
    __table_args__ = (
        UniqueConstraint("session_id", "ordinal", name="lecture_voice_turns_session_ordinal_uq"),
        CheckConstraint("ordinal >= 0", name="lecture_voice_turns_ordinal_nonneg_check"),
        Index("ix_lecture_voice_turns_session_id", "session_id"),
        {"schema": "independent"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("independent.lecture_voice_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    transcript: Mapped[str] = mapped_column(Text, nullable=False)
    ai_response_text: Mapped[str] = mapped_column(Text, nullable=False)
    edit_operation_jsonb: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    audio_storage_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    audio_purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        super().__init__(**kwargs)


class IndependentLectureDraft(AuditMixin, SoftDeleteMixin, Base):
    """Wizard auto-save for independent teachers."""

    __tablename__ = "lecture_drafts"
    __table_args__ = (
        Index(
            "lecture_drafts_teacher_user_id_uq",
            "teacher_user_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        {"schema": "independent"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid7)
    teacher_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("independent.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    wizard_state_jsonb: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)

    def __init__(self, **kwargs: object) -> None:
        if "id" not in kwargs:
            kwargs["id"] = _uuid7()
        if "wizard_state_jsonb" not in kwargs:
            kwargs["wizard_state_jsonb"] = {"step": 1, "data": {}}
        super().__init__(**kwargs)
