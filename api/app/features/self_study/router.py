"""Self-study entry, session, due-flashcards, goals, materials API — T-209–T-212."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import ValidationError
from app.core.responses import SuccessEnvelope, success
from app.features.self_study.adherence import SelfStudyAdherenceService
from app.features.self_study.categorisation import (
    PREP_BOOK_GATE_ERROR,
    SelfStudyCategorisationService,
)
from app.features.self_study.goals import SelfStudyGoalService
from app.features.self_study.materials import SelfStudyMaterialService
from app.features.self_study.plans import SelfStudyPlanService
from app.features.self_study.reminders import SelfStudyReminderService
from app.features.self_study.schemas import (
    AdherenceSummaryRead,
    DueFlashcardsListRead,
    GoogleCalendarConfigRead,
    PrepBookGateRead,
    PrepBookTopicListRead,
    ReminderPreferencesRead,
    ReminderPreferencesUpdate,
    SelfStudyEntryRead,
    SelfStudyGoalAchieve,
    SelfStudyGoalRead,
    SelfStudyGoalSet,
    SelfStudyGoalTodayRead,
    SelfStudyMaterialCategorise,
    SelfStudyMaterialListRead,
    SelfStudyMaterialRead,
    SelfStudyMaterialTypedCreate,
    SelfStudyMaterialUploadResult,
    SelfStudySessionRead,
    SelfStudySessionStart,
    SelfStudyStateUpdate,
    StudyPlanActiveRead,
    StudyPlanConversationAnswer,
    StudyPlanConversationRead,
    StudyPlanRead,
    StudyPlanRefineRequest,
)
from app.features.self_study.service import SelfStudyEntryService
from app.features.self_study.session_service import SelfStudySessionService
from app.features.self_study.topics import SelfStudyTopicService

router = APIRouter(prefix="/self-study/me", tags=["self-study"])


@router.get(
    "/entry",
    response_model=SuccessEnvelope[SelfStudyEntryRead],
    operation_id="self_study_get_entry",
    summary="Enter self-study mode (resume state; independent redirects)",
)
async def get_entry(
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = SelfStudyEntryService(db)
    entry = await svc.get_entry(claims)
    return success(entry.model_dump())


@router.patch(
    "/state",
    response_model=SuccessEnvelope[SelfStudyEntryRead],
    operation_id="self_study_patch_state",
    summary="Persist last goal / material / plan view for self-study",
)
async def patch_state(
    payload: SelfStudyStateUpdate,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = SelfStudyEntryService(db)
    entry = await svc.update_state(payload, claims)
    return success(entry.model_dump())


@router.post(
    "/sessions",
    response_model=SuccessEnvelope[SelfStudySessionRead],
    operation_id="self_study_start_session",
    summary="Start a self-study session (Flow 6 reuse; mode=self_study events)",
)
async def start_session(
    payload: SelfStudySessionStart,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = SelfStudySessionService(db)
    row = await svc.start_session(payload, claims)
    return success(row.model_dump())


@router.post(
    "/sessions/{session_id}/end",
    response_model=SuccessEnvelope[SelfStudySessionRead],
    operation_id="self_study_end_session",
    summary="End a self-study session",
)
async def end_session(
    session_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = SelfStudySessionService(db)
    row = await svc.end_session(session_id, claims)
    return success(row.model_dump())


@router.get(
    "/due-flashcards",
    response_model=SuccessEnvelope[DueFlashcardsListRead],
    operation_id="self_study_list_due_flashcards",
    summary="Read-only due flashcards deck (schedule owned by Flow 9)",
)
async def list_due_flashcards(
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = SelfStudySessionService(db)
    deck = await svc.list_due_flashcards(claims)
    return success(deck.model_dump())


@router.get(
    "/goal",
    response_model=SuccessEnvelope[SelfStudyGoalTodayRead],
    operation_id="self_study_get_today_goal",
    summary="Get today's self-study goal (Asia/Karachi)",
)
async def get_today_goal(
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = SelfStudyGoalService(db)
    goal = await svc.get_today(claims)
    return success(SelfStudyGoalTodayRead(goal=goal).model_dump())


@router.put(
    "/goal",
    response_model=SuccessEnvelope[SelfStudyGoalRead],
    operation_id="self_study_set_goal",
    summary="Set or replace today's free-text daily goal",
)
async def set_goal(
    payload: SelfStudyGoalSet,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = SelfStudyGoalService(db)
    goal = await svc.set_goal(payload, claims)
    return success(goal.model_dump())


@router.post(
    "/goal/achievement",
    response_model=SuccessEnvelope[SelfStudyGoalRead],
    operation_id="self_study_goal_achievement",
    summary="End-of-session goal check (once/day, skippable, >5 min)",
)
async def goal_achievement(
    payload: SelfStudyGoalAchieve,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = SelfStudyGoalService(db)
    goal = await svc.respond_achievement(
        payload,
        claims,
        session_duration_seconds=payload.session_duration_seconds,
    )
    return success(goal.model_dump())


@router.get(
    "/materials",
    response_model=SuccessEnvelope[SelfStudyMaterialListRead],
    operation_id="self_study_list_materials",
    summary="List own Study Library materials (private personal pool)",
)
async def list_materials(
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = SelfStudyMaterialService(db)
    deck = await svc.list_library(claims)
    return success(deck.model_dump())


@router.post(
    "/materials/upload",
    response_model=SuccessEnvelope[SelfStudyMaterialUploadResult],
    operation_id="self_study_upload_material",
    summary="Upload PDF/camera/gallery material (Instant Answer or Add to Library)",
)
async def upload_material(
    file: UploadFile = File(...),
    source_type: Literal["pdf", "camera", "gallery"] = Form(...),
    disposition: Literal["instant_answer", "add_to_library"] = Form(...),
    title: str = Form("Untitled material"),
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    data = await file.read()
    if not data:
        raise ValidationError("Empty file")
    filename = file.filename or "upload.bin"
    svc = SelfStudyMaterialService(db)
    result = await svc.upload_file(
        claims,
        data=data,
        filename=filename,
        source_type=source_type,
        disposition=disposition,
        title=title,
    )
    return success(result.model_dump())


@router.post(
    "/materials/typed",
    response_model=SuccessEnvelope[SelfStudyMaterialUploadResult],
    operation_id="self_study_typed_material",
    summary="Typed material via hybrid widget (Instant Answer or Add to Library)",
)
async def typed_material(
    payload: SelfStudyMaterialTypedCreate,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = SelfStudyMaterialService(db)
    result = await svc.submit_typed(claims, payload)
    return success(result.model_dump())


@router.patch(
    "/materials/{material_id}/book-type",
    response_model=SuccessEnvelope[SelfStudyMaterialRead],
    operation_id="self_study_categorise_material",
    summary="Categorise library material (prep_questions | reference_content)",
)
async def categorise_material(
    material_id: str,
    payload: SelfStudyMaterialCategorise,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = SelfStudyCategorisationService(db)
    row = await svc.categorise(claims, material_id=material_id, book_type=payload.book_type)
    # T-214 — enqueue topic extraction for prep books (non-blocking).
    if payload.book_type == "prep_questions":
        try:
            from app.core.tenant import get_tenant_type
            from app.features.self_study.tasks import extract_topics

            tenant = get_tenant_type(claims)
            # Ownership id is the student FK on the material row — re-fetch via topics sync
            # path when Celery is down; delay uses JWT sub as school_id for independent.
            extract_topics.delay(
                school_id=str(claims.get("school_id") or claims.get("sub") or "unknown"),
                material_id=material_id,
                student_user_id="",
                tenant_type=tenant,
                authentik_id=str(claims.get("sub") or ""),
            )
        except Exception:  # noqa: BLE001 — Celery may be unavailable in tests
            pass
    return success(row.model_dump())


@router.get(
    "/plans/gate",
    response_model=SuccessEnvelope[PrepBookGateRead],
    operation_id="self_study_prep_book_gate",
    summary="Check prep-book hard gate for plan generation",
)
async def prep_book_gate(
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = SelfStudyCategorisationService(db)
    ok = await svc.has_prep_book(claims)
    return success(
        PrepBookGateRead(
            has_prep_book=ok,
            allowed=ok,
            error_message=None if ok else PREP_BOOK_GATE_ERROR,
        ).model_dump()
    )


@router.post(
    "/materials/{material_id}/extract-topics",
    response_model=SuccessEnvelope[PrepBookTopicListRead],
    operation_id="self_study_extract_topics",
    summary="Extract weighted topics from a prep book (sync path for tests)",
)
async def extract_topics_sync(
    material_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = SelfStudyTopicService(db)
    result = await svc.extract_for_claims(claims, material_id=material_id)
    return success(result.model_dump())


@router.get(
    "/plans/conversation",
    response_model=SuccessEnvelope[StudyPlanConversationRead],
    operation_id="self_study_plan_conversation_state",
    summary="Conversational plan wizard state (5 questions)",
)
async def plan_conversation_state(
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = SelfStudyPlanService(db)
    state = await svc.conversation_state(claims)
    return success(state.model_dump())


@router.post(
    "/plans/conversation",
    response_model=SuccessEnvelope[StudyPlanConversationRead],
    operation_id="self_study_plan_conversation_answer",
    summary="Answer the next conversational plan question",
)
async def plan_conversation_answer(
    payload: StudyPlanConversationAnswer,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = SelfStudyPlanService(db)
    state = await svc.answer_conversation(claims, payload)
    return success(state.model_dump())


@router.post(
    "/plans/generate",
    response_model=SuccessEnvelope[StudyPlanRead],
    operation_id="self_study_generate_plan",
    summary="Generate study plan from conversation + weighted topics",
)
async def generate_plan(
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = SelfStudyPlanService(db)
    plan = await svc.generate(claims)
    return success(plan.model_dump())


@router.get(
    "/plans/active",
    response_model=SuccessEnvelope[StudyPlanActiveRead],
    operation_id="self_study_get_active_plan",
    summary="Get the student's active study plan",
)
async def get_active_plan(
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = SelfStudyPlanService(db)
    plan = await svc.get_active(claims)
    return success(StudyPlanActiveRead(plan=plan).model_dump())


@router.post(
    "/plans/{plan_id}/refine",
    response_model=SuccessEnvelope[StudyPlanRead],
    operation_id="self_study_refine_plan",
    summary="Natural-language refine of affected plan items",
)
async def refine_plan(
    plan_id: str,
    payload: StudyPlanRefineRequest,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = SelfStudyPlanService(db)
    plan = await svc.refine(claims, plan_id, payload)
    return success(plan.model_dump())


@router.get(
    "/plans/{plan_id}/calendar.ics",
    response_model=None,
    operation_id="self_study_export_ics",
    summary="Export study plan as .ics (always available)",
)
async def export_ics(
    plan_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PlainTextResponse:
    svc = SelfStudyPlanService(db)
    body = await svc.export_ics(claims, plan_id)
    return PlainTextResponse(
        content=body,
        media_type="text/calendar",
        headers={"Content-Disposition": f'attachment; filename="study-plan-{plan_id}.ics"'},
    )


@router.get(
    "/calendar/google-config",
    response_model=SuccessEnvelope[GoogleCalendarConfigRead],
    operation_id="self_study_google_calendar_config",
    summary="Whether Google Calendar OAuth button is enabled",
)
async def google_calendar_config(
    claims: dict[str, object] = Depends(get_current_user),
) -> dict[str, Any]:
    _ = claims
    settings = get_settings()
    enabled = bool(getattr(settings, "GOOGLE_CALENDAR_SYNC_ENABLED", False))
    return success(GoogleCalendarConfigRead(enabled=enabled).model_dump())


@router.get(
    "/reminder-preferences",
    response_model=SuccessEnvelope[ReminderPreferencesRead],
    operation_id="self_study_get_reminder_preferences",
    summary="Get reminder channel preferences",
)
async def get_reminder_preferences(
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = SelfStudyReminderService(db)
    prefs = await svc.get_prefs(claims)
    return success(prefs.model_dump())


@router.put(
    "/reminder-preferences",
    response_model=SuccessEnvelope[ReminderPreferencesRead],
    operation_id="self_study_put_reminder_preferences",
    summary="Update reminder channel preferences",
)
async def put_reminder_preferences(
    payload: ReminderPreferencesUpdate,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = SelfStudyReminderService(db)
    prefs = await svc.update_prefs(claims, payload)
    return success(prefs.model_dump())


@router.post(
    "/plans/{plan_id}/adherence/check",
    response_model=SuccessEnvelope[AdherenceSummaryRead],
    operation_id="self_study_check_adherence",
    summary="Run adherence check for a plan day (activity-inferred)",
)
async def check_adherence(
    plan_id: str,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    svc = SelfStudyAdherenceService(db)
    summary = await svc.check_for_claims(claims, plan_id=plan_id)
    return success(summary.model_dump())
