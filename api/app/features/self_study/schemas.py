"""Pydantic schemas for self-study entry + state persistence — T-209."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SelfStudyPersistedState(BaseModel):
    """Last-view keys restored when entering self-study (Flow 8 §3.1)."""

    model_config = ConfigDict(extra="forbid")

    last_goal_id: str | None = None
    last_material_id: str | None = None
    last_plan_view: str | None = None


class SelfStudySubscriptionGateRead(BaseModel):
    """No-op gate at launch — limits unset until Flow 13 / M-23."""

    enforced: bool = False
    allowed: bool = True
    max_active_plans: int | None = None
    max_monthly_uploads: int | None = None


class SelfStudyEntryRead(BaseModel):
    """Entering-mode payload for school + independent students."""

    tenant_type: Literal["school", "independent"]
    locked_to_self_study: bool
    active_mode: Literal["lecture", "self_study"]
    state: SelfStudyPersistedState
    subscription_gate: SelfStudySubscriptionGateRead
    # Independent: Lecture-Mode routes must redirect here.
    lecture_mode_redirect_to: str | None = None


class SelfStudyStateUpdate(BaseModel):
    """Partial update of persisted self-study view keys."""

    model_config = ConfigDict(extra="forbid")

    last_goal_id: str | None = Field(default=None)
    last_material_id: str | None = Field(default=None)
    last_plan_view: str | None = Field(default=None)


class SelfStudySessionStart(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_id: str | None = None
    study_plan_id: str | None = None


class SelfStudySessionRead(BaseModel):
    id: str
    tenant_type: Literal["school", "independent"]
    mode: Literal["self_study"]
    status: Literal["active", "ended"]
    material_id: str | None = None
    study_plan_id: str | None = None
    # Retrieval plan summary (Pattern A + personal pool + overlays).
    retrieval_primary: Literal["student_upload_chunks"]
    retrieval_overlays: list[str]
    reaches_flow7: bool


class DueFlashcardRead(BaseModel):
    """Read-only due card — schedule owned by Flow 9 (py-fsrs not computed here)."""

    id: str
    front_text: str
    back_text: str
    concept_tag: str | None = None
    # Always null until M-18 owns scheduling (py-fsrs).
    due_at: str | None = None


class DueFlashcardsListRead(BaseModel):
    items: list[DueFlashcardRead]
    schedule_computed: bool = False
    schedule_owner: Literal["flow_9"] = "flow_9"


class SelfStudyGoalRead(BaseModel):
    id: str
    tenant_type: Literal["school", "independent"]
    goal_date: str
    goal_text: str
    achieved: bool | None = None
    achievement_check_pending: bool = True


class SelfStudyGoalTodayRead(BaseModel):
    """Wrapper so OpenAPI stays accurate when no goal is set."""

    goal: SelfStudyGoalRead | None = None


class SelfStudyGoalSet(BaseModel):
    """Free-text daily goal via hybrid widget (no templates)."""

    model_config = ConfigDict(extra="forbid")

    goal_text: str = Field(min_length=1, max_length=2000)
    confirm_replace: bool = False


class SelfStudyGoalAchieve(BaseModel):
    """End-of-session achievement check (skippable)."""

    model_config = ConfigDict(extra="forbid")

    achieved: bool | None = None
    skip: bool = False
    session_duration_seconds: int = Field(ge=0, default=0)


class SelfStudyMaterialRead(BaseModel):
    id: str
    tenant_type: Literal["school", "independent"]
    title: str
    source_type: Literal["pdf", "camera", "gallery", "typed"]
    book_type: Literal["prep_questions", "reference_content"] | None = None
    added_to_library: bool
    storage_key: str | None = None
    has_ocr_text: bool = False


class SelfStudyMaterialListRead(BaseModel):
    items: list[SelfStudyMaterialRead]


class SelfStudyMaterialTypedCreate(BaseModel):
    """Typed path — hybrid widget #57 text, no file."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=20000)
    title: str = Field(default="Typed note", min_length=1, max_length=500)
    disposition: Literal["instant_answer", "add_to_library"]


class SelfStudyMaterialUploadResult(BaseModel):
    """Post-upload Instant Answer or Add-to-Library result."""

    disposition: Literal["instant_answer", "add_to_library"]
    source_type: Literal["pdf", "camera", "gallery", "typed"]
    extraction_method: Literal["pdfplumber", "paddleocr", "tesseract", "typed"] | None = None
    # Present only when add_to_library persisted a private-pool row.
    material: SelfStudyMaterialRead | None = None
    # Instant Answer: ephemeral answer (not a library row).
    instant_answer_text: str | None = None
    extracted_text_preview: str | None = None
    event_emitted: bool = True


class SelfStudyMaterialCategorise(BaseModel):
    model_config = ConfigDict(extra="forbid")

    book_type: Literal["prep_questions", "reference_content"]


class PrepBookGateRead(BaseModel):
    has_prep_book: bool
    allowed: bool
    error_message: str | None = None


class PrepBookTopicRead(BaseModel):
    id: str
    topic_label: str
    question_count: int
    weight: float
    curriculum_topic_id: str | None = None


class PrepBookTopicListRead(BaseModel):
    material_id: str
    items: list[PrepBookTopicRead]
    partial_parse: bool = False
    overflow_flagged: bool = False
    banner: str | None = None


class StudyPlanConversationAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str = Field(min_length=1, max_length=2000)


class StudyPlanConversationRead(BaseModel):
    step: int
    total_steps: int
    question: str | None = None
    answers: dict[str, str]
    complete: bool
    gate_passed: bool = True


class StudyPlanItemRead(BaseModel):
    id: str
    granularity: Literal["day", "3day", "week"]
    start_date: str
    end_date: str
    est_minutes: int
    subject_color: str
    tasks: list[object]


class StudyPlanRead(BaseModel):
    id: str
    tenant_type: Literal["school", "independent"]
    status: Literal["active", "archived"]
    exam_date: str | None = None
    daily_hours: int
    strong_topics: list[str]
    granularity_current: Literal["day", "3day", "week"]
    items: list[StudyPlanItemRead]


class StudyPlanActiveRead(BaseModel):
    plan: StudyPlanRead | None = None


class StudyPlanRefineRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refinement_request: str = Field(min_length=1, max_length=2000)


class ReminderPreferencesRead(BaseModel):
    push_enabled: bool
    email_enabled: bool
    sms_enabled: bool
    timezone: str


class ReminderPreferencesUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    push_enabled: bool | None = None
    email_enabled: bool | None = None
    sms_enabled: bool | None = None
    timezone: str | None = Field(default=None, max_length=64)


class GoogleCalendarConfigRead(BaseModel):
    """Env-gated Google Calendar OAuth — hidden when unconfigured (T-217)."""

    enabled: bool


class AdherenceDayRead(BaseModel):
    day_date: str
    adherence_pct: float
    consecutive_miss_count: int
    alerted: bool


class AdherenceSummaryRead(BaseModel):
    plan_id: str
    days: list[AdherenceDayRead]
    alert_fired: bool = False
