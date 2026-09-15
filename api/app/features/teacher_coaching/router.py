"""Teaching Innovation Record + benchmarking API — school tenant (T-138 Flow 5
§3.10 #36, T-139 §3.11 #37). Benchmarking is school-only: no peer cohort
exists within a one-person independent tenant (benchmark_service module
docstring)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.core.responses import SuccessEnvelope, success
from app.features.audit.actions import BENCHMARK_OPT_OUT_TOGGLED
from app.features.teacher_coaching import benchmark_service, service
from app.features.teacher_coaching.schemas import (
    BenchmarkOptOutRequest,
    CoachingResponseRequest,
    CoachingSuggestionRead,
    TeacherBenchmarkRead,
)
from app.infrastructure.audit.log import audit

router = APIRouter(prefix="/teachers/me/coaching", tags=["teacher-coaching"])
benchmarks_router = APIRouter(prefix="/teachers/me/benchmarks", tags=["teacher-coaching"])


@router.get(
    "",
    response_model=SuccessEnvelope[list[CoachingSuggestionRead]],
    operation_id="teacher_list_coaching_suggestions",
    summary="Pending (unactioned) coaching tips — the Teaching Innovation Record (T-138, #36)",
    dependencies=[require_role("teacher")],
)
async def list_coaching_suggestions(
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    teacher_id = await service.resolve_school_teacher_id(db, claims)
    rows = await service.list_current_suggestions_school(db, teacher_id)
    return success([service.to_suggestion_read(row).model_dump(mode="json") for row in rows])


@router.post(
    "/{memory_id}/respond",
    response_model=SuccessEnvelope[CoachingSuggestionRead],
    operation_id="teacher_respond_to_coaching_suggestion",
    summary="Mark a coaching tip acted-on or ignored (T-138, #36)",
    dependencies=[require_role("teacher")],
)
async def respond_to_coaching_suggestion(
    memory_id: str,
    payload: CoachingResponseRequest,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    teacher_id = await service.resolve_school_teacher_id(db, claims)
    memory = await service.respond_to_suggestion_school(
        db, teacher_user_id=teacher_id, memory_id=memory_id, response=payload.response
    )
    return success(service.to_suggestion_read(memory).model_dump(mode="json"))


@benchmarks_router.get(
    "",
    response_model=SuccessEnvelope[list[TeacherBenchmarkRead]],
    operation_id="teacher_list_benchmarks",
    summary='Positively-framed peer-cohort standing, e.g. "Top 23%" (T-139, #37)',
    dependencies=[require_role("teacher")],
)
async def list_benchmarks(
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    teacher_id = await service.resolve_school_teacher_id(db, claims)
    rows = await benchmark_service.get_teacher_benchmarks(db, teacher_id)
    return success(
        [TeacherBenchmarkRead.model_validate(row).model_dump(mode="json") for row in rows]
    )


@benchmarks_router.post(
    "/opt-out",
    response_model=SuccessEnvelope[dict[str, int]],
    operation_id="teacher_set_benchmark_opt_out",
    summary="Opt in/out of anonymized peer benchmarking (T-139, #37)",
    dependencies=[require_role("teacher")],
)
async def set_benchmark_opt_out(
    payload: BenchmarkOptOutRequest,
    claims: dict[str, object] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    teacher_id = await service.resolve_school_teacher_id(db, claims)
    rows_changed = await benchmark_service.set_benchmark_opt_out(
        db, teacher_user_id=teacher_id, opted_out=payload.opted_out
    )
    await audit(
        session=db,
        action=BENCHMARK_OPT_OUT_TOGGLED,
        actor_id=str(claims.get("sub", "")),
        actor_role=str(claims.get("role", "")),
        target_type="teacher_benchmark",
        target_id=teacher_id,
        school_id=str(claims["school_id"]) if claims.get("school_id") else None,
        metadata={"opted_out": payload.opted_out, "rows_changed": rows_changed},
    )
    return success({"rows_changed": rows_changed})
