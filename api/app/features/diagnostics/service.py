"""Diagnostic lifecycle service — T-103 (Flow 4 §3.6).

States: not_taken → in_progress → completed.
Save/resume within 7 days (expires_at). Retake = new attempt after 30-day cooldown.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Literal, cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PreconditionFailedError, ValidationError
from app.core.tenant import TenantType
from app.features.audit.actions import (
    COGNITIVE_DNA_SEEDED,
    DIAGNOSTIC_COMPLETED,
    DIAGNOSTIC_RETAKEN,
    DIAGNOSTIC_STARTED,
)
from app.features.cognitive_dna.repository import CognitiveDnaRepository
from app.features.diagnostics.dna_seed import build_topic_confidence, focus_areas_to_jsonb
from app.features.diagnostics.events import publish_diagnostic_completed
from app.features.diagnostics.focus_areas import derive_focus_areas
from app.features.diagnostics.models import (
    DiagnosticStatus,
    DiagnosticTenantType,
    IndependentDiagnostic,
    SchoolDiagnostic,
)
from app.features.diagnostics.question_generation import generate_diagnostic_questions
from app.features.diagnostics.repository import DiagnosticRepository, DiagnosticRow
from app.features.diagnostics.schemas import (
    DiagnosticAnswersBlob,
    DiagnosticQuestionsBlob,
    DiagnosticRead,
    DiagnosticResultRead,
)
from app.infrastructure.audit.log import audit

RESUME_WINDOW = timedelta(days=7)
RETAKE_COOLDOWN = timedelta(days=30)
RETAKE_BLOCKED_MESSAGE = (
    "Retake is available 30 days after your last completed diagnostic for this topic"
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DiagnosticService:
    def __init__(self, session: AsyncSession, tenant_type: TenantType) -> None:
        self._session = session
        self._tenant_type = tenant_type
        self._repo = DiagnosticRepository(session, tenant_type)
        self._dna_repo = CognitiveDnaRepository(session, tenant_type)

    def _validate_scope(self, subject_id: str | None, framework_id: str | None) -> None:
        if self._tenant_type == "school":
            if not subject_id:
                raise ValidationError("School diagnostics require subject_id")
            if framework_id:
                raise ValidationError("School diagnostics must not set framework_id")
        else:
            if not framework_id:
                raise ValidationError("Independent diagnostics require framework_id")
            if subject_id:
                raise ValidationError("Independent diagnostics must not set subject_id")

    def _to_read(self, row: DiagnosticRow) -> DiagnosticRead:
        questions = DiagnosticQuestionsBlob.from_jsonb(row.questions_jsonb)
        answers = DiagnosticAnswersBlob.from_jsonb(row.answers_jsonb)
        return DiagnosticRead(
            id=row.id,
            tenant_type=cast(Any, row.tenant_type.value),
            student_user_id=row.student_user_id,
            subject_id=row.subject_id,
            framework_id=row.framework_id,
            status=cast(Any, row.status.value),
            questions=questions.questions,
            answers=answers.answers,
            started_at=row.started_at,
            completed_at=row.completed_at,
            expires_at=row.expires_at,
        )

    def _is_expired(self, row: DiagnosticRow, now: datetime) -> bool:
        return (
            row.status == DiagnosticStatus.IN_PROGRESS
            and row.expires_at is not None
            and now >= row.expires_at
        )

    async def _latest_completed(
        self,
        *,
        student_user_id: str,
        subject_id: str | None,
        framework_id: str | None,
    ) -> DiagnosticRow | None:
        rows = await self._repo.list_for_scope(
            student_user_id=student_user_id,
            subject_id=subject_id,
            framework_id=framework_id,
        )
        completed = [
            r for r in rows if r.status == DiagnosticStatus.COMPLETED and r.completed_at is not None
        ]
        if not completed:
            return None
        return max(
            completed, key=lambda r: r.completed_at or datetime.min.replace(tzinfo=timezone.utc)
        )

    async def _active_in_progress(
        self,
        *,
        student_user_id: str,
        subject_id: str | None,
        framework_id: str | None,
        now: datetime,
    ) -> DiagnosticRow | None:
        rows = await self._repo.list_for_scope(
            student_user_id=student_user_id,
            subject_id=subject_id,
            framework_id=framework_id,
        )
        for row in rows:
            if row.status == DiagnosticStatus.IN_PROGRESS and not self._is_expired(row, now):
                return row
        return None

    def _assert_cooldown(self, completed: DiagnosticRow | None, now: datetime) -> None:
        if completed is None or completed.completed_at is None:
            return
        if now < completed.completed_at + RETAKE_COOLDOWN:
            raise PreconditionFailedError(RETAKE_BLOCKED_MESSAGE)

    async def start(
        self,
        *,
        student_user_id: str,
        subject_id: str | None = None,
        framework_id: str | None = None,
        questions: list[object] | None = None,
    ) -> DiagnosticRead:
        self._validate_scope(subject_id, framework_id)
        now = _utcnow()

        active = await self._active_in_progress(
            student_user_id=student_user_id,
            subject_id=subject_id,
            framework_id=framework_id,
            now=now,
        )
        if active is not None:
            return self._to_read(active)

        latest = await self._latest_completed(
            student_user_id=student_user_id,
            subject_id=subject_id,
            framework_id=framework_id,
        )
        self._assert_cooldown(latest, now)
        is_retake = latest is not None

        questions_blob = DiagnosticQuestionsBlob.from_jsonb(questions)
        if self._tenant_type == "school":
            row: DiagnosticRow = SchoolDiagnostic(
                student_user_id=student_user_id,
                subject_id=subject_id,
                tenant_type=DiagnosticTenantType.SCHOOL,
                status=DiagnosticStatus.IN_PROGRESS,
                questions_jsonb=questions_blob.to_jsonb(),
                answers_jsonb={},
                started_at=now,
                expires_at=now + RESUME_WINDOW,
            )
        else:
            row = IndependentDiagnostic(
                student_user_id=student_user_id,
                framework_id=framework_id,
                tenant_type=DiagnosticTenantType.INDEPENDENT,
                status=DiagnosticStatus.IN_PROGRESS,
                questions_jsonb=questions_blob.to_jsonb(),
                answers_jsonb={},
                started_at=now,
                expires_at=now + RESUME_WINDOW,
            )
        created = await self._repo.create(row)
        await self._audit_lifecycle(
            action=DIAGNOSTIC_RETAKEN if is_retake else DIAGNOSTIC_STARTED,
            student_user_id=student_user_id,
            diagnostic_id=created.id,
            subject_id=subject_id,
            framework_id=framework_id,
            extra={"retake": is_retake},
        )
        return self._to_read(created)

    async def save_answers(
        self,
        *,
        diagnostic_id: str,
        answers: dict[str, Any],
    ) -> DiagnosticRead:
        row = await self._repo.get_by_id(diagnostic_id)
        if row is None:
            raise PreconditionFailedError("Diagnostic not found or expired")
        now = _utcnow()
        if row.status != DiagnosticStatus.IN_PROGRESS:
            raise PreconditionFailedError("Diagnostic is not in progress")
        if self._is_expired(row, now):
            raise PreconditionFailedError("Diagnostic expired — start a new attempt")

        merged = DiagnosticAnswersBlob.from_jsonb(row.answers_jsonb)
        merged.answers.update(answers)
        row.answers_jsonb = merged.to_jsonb()
        updated = await self._repo.update(row)
        return self._to_read(updated)

    async def resume(self, *, diagnostic_id: str) -> DiagnosticRead:
        row = await self._repo.get_by_id(diagnostic_id)
        if row is None:
            raise PreconditionFailedError("Diagnostic not found or expired")
        now = _utcnow()
        if row.status != DiagnosticStatus.IN_PROGRESS:
            raise PreconditionFailedError("Diagnostic is not in progress")
        if self._is_expired(row, now):
            raise PreconditionFailedError("Diagnostic expired — start a new attempt")
        return self._to_read(row)

    async def complete(self, *, diagnostic_id: str) -> DiagnosticResultRead:
        row = await self._repo.get_by_id(diagnostic_id)
        if row is None:
            raise PreconditionFailedError("Diagnostic not found or expired")
        now = _utcnow()
        if row.status == DiagnosticStatus.COMPLETED:
            return self._to_result(row, timed_out=False)
        if row.status != DiagnosticStatus.IN_PROGRESS:
            raise PreconditionFailedError("Diagnostic is not in progress")
        if self._is_expired(row, now):
            return await self.finalize_timeout(diagnostic_id=diagnostic_id)

        row.status = DiagnosticStatus.COMPLETED
        row.completed_at = now
        updated = await self._repo.update(row)
        return await self._seed_dna_and_result(updated, timed_out=False)

    async def finalize_timeout(self, *, diagnostic_id: str) -> DiagnosticResultRead:
        """Gracefully complete an expired in-progress diagnostic (T-105 acceptance)."""
        row = await self._repo.get_by_id(diagnostic_id)
        if row is None:
            raise PreconditionFailedError("Diagnostic not found or expired")
        if row.status == DiagnosticStatus.COMPLETED:
            return self._to_result(row, timed_out=True)
        if row.status != DiagnosticStatus.IN_PROGRESS:
            raise PreconditionFailedError("Diagnostic is not in progress")

        row.status = DiagnosticStatus.COMPLETED
        row.completed_at = _utcnow()
        updated = await self._repo.update(row)
        return await self._seed_dna_and_result(updated, timed_out=True)

    async def _seed_dna_and_result(
        self, row: DiagnosticRow, *, timed_out: bool
    ) -> DiagnosticResultRead:
        """After COMPLETED commit: upsert Cognitive DNA + emit NATS (T-106)."""
        result = self._to_result(row, timed_out=timed_out)
        confidence = build_topic_confidence(
            questions=result.diagnostic.questions,
            answers=result.diagnostic.answers,
        )
        await self._dna_repo.upsert_from_diagnostic(
            student_user_id=row.student_user_id,
            subject_id=row.subject_id,
            framework_id=row.framework_id,
            topic_confidence_jsonb=confidence,
            focus_areas_jsonb=focus_areas_to_jsonb(result.focus_areas),
            now=row.completed_at or _utcnow(),
        )
        await self._audit_lifecycle(
            action=DIAGNOSTIC_COMPLETED,
            student_user_id=row.student_user_id,
            diagnostic_id=row.id,
            subject_id=row.subject_id,
            framework_id=row.framework_id,
            extra={"timed_out": timed_out},
        )
        await self._audit_lifecycle(
            action=COGNITIVE_DNA_SEEDED,
            student_user_id=row.student_user_id,
            diagnostic_id=row.id,
            subject_id=row.subject_id,
            framework_id=row.framework_id,
            extra={
                "focus_area_count": len(result.focus_areas),
                "source": "diagnostic",
            },
        )
        tenant_kind: Literal["school", "independent"] = (
            "independent" if self._tenant_type == "independent" else "school"
        )
        completed_iso = row.completed_at.isoformat() if row.completed_at else None
        await publish_diagnostic_completed(
            diagnostic_id=row.id,
            student_user_id=row.student_user_id,
            tenant_type=tenant_kind,
            subject_id=row.subject_id,
            framework_id=row.framework_id,
            completed_at=completed_iso,
            timed_out=timed_out,
        )
        await self._notify_completed(row, result)
        return result

    async def _audit_lifecycle(
        self,
        *,
        action: str,
        student_user_id: str,
        diagnostic_id: str,
        subject_id: str | None,
        framework_id: str | None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Synchronous audit write for diagnostic/DNA transitions (T-110 / ARCH §14.10)."""
        school_id: str | None = None
        if self._tenant_type != "independent":
            from app.features.users.repository import UserRepository

            user = await UserRepository(self._session).get_by_id(student_user_id)
            if user is not None:
                school_id = user.school_id
        metadata: dict[str, Any] = {
            "tenant_type": ("independent" if self._tenant_type == "independent" else "school"),
            "subject_id": subject_id,
            "framework_id": framework_id,
        }
        if extra:
            metadata.update(extra)
        await audit(
            session=self._session,
            action=action,
            actor_id=student_user_id,
            target_type="diagnostic",
            target_id=diagnostic_id,
            school_id=school_id,
            metadata=metadata,
        )

    async def _resolve_notify_recipient(
        self, student_user_id: str
    ) -> tuple[str | None, str | None, str]:
        """Return (authentik_id, school_id, locale) for diagnostic notifications."""
        from app.features.independent_student_onboarding.repository import (
            IndependentStudentProfileRepository,
        )
        from app.features.independent_users.repository import IndependentUserRepository
        from app.features.student_onboarding.repository import StudentProfileRepository
        from app.features.users.repository import UserRepository

        if self._tenant_type == "independent":
            ind_user = await IndependentUserRepository(self._session).get_by_id(student_user_id)
            ind_profile = await IndependentStudentProfileRepository(self._session).get_by_user_id(
                student_user_id
            )
            recipient = ind_user.authentik_id if ind_user is not None else None
            locale = ind_profile.language_preference if ind_profile is not None else "en"
            return recipient, None, locale

        school_user = await UserRepository(self._session).get_by_id(student_user_id)
        school_profile = await StudentProfileRepository(self._session).get_by_user_id(
            student_user_id
        )
        recipient = school_user.authentik_id if school_user is not None else None
        school_id = school_user.school_id if school_user is not None else None
        locale = school_profile.language_preference if school_profile is not None else "en"
        return recipient, school_id, locale

    async def _notify_completed(self, row: DiagnosticRow, result: DiagnosticResultRead) -> None:
        """In-app focus-areas summary (T-109); never grades."""
        from app.features.diagnostics.notifications import (
            notify_diagnostic_completed,
            safe_notify,
        )

        recipient, school_id, locale = await self._resolve_notify_recipient(row.student_user_id)
        if not recipient:
            return
        await safe_notify(
            notify_diagnostic_completed(
                session=self._session,
                recipient_user_id=recipient,
                school_id=school_id,
                locale=locale,
                focus_areas=result.focus_areas,
                diagnostic_id=row.id,
            )
        )

    async def send_retake_available_notifications(self) -> int:
        """Notify students whose 30-day retake cooldown has elapsed (T-109)."""
        from app.features.diagnostics.notifications import (
            notify_diagnostic_retake_available,
            safe_notify,
        )

        cutoff = _utcnow() - RETAKE_COOLDOWN
        candidates = await self._repo.list_retake_notify_candidates(cooldown_elapsed_before=cutoff)
        count = 0
        now = _utcnow()
        for row in candidates:
            # Skip if a newer attempt already exists for the same scope.
            siblings = await self._repo.list_for_scope(
                student_user_id=row.student_user_id,
                subject_id=row.subject_id,
                framework_id=row.framework_id,
            )
            if any(
                s.id != row.id
                and s.started_at is not None
                and row.completed_at is not None
                and s.started_at > row.completed_at
                for s in siblings
            ):
                row.retake_available_notified_at = now
                await self._repo.update(row)
                continue

            recipient, school_id, locale = await self._resolve_notify_recipient(row.student_user_id)
            if recipient:
                await safe_notify(
                    notify_diagnostic_retake_available(
                        session=self._session,
                        recipient_user_id=recipient,
                        school_id=school_id,
                        locale=locale,
                        diagnostic_id=row.id,
                    )
                )
                count += 1
            row.retake_available_notified_at = now
            await self._repo.update(row)
        return count

    def _to_result(self, row: DiagnosticRow, *, timed_out: bool) -> DiagnosticResultRead:
        read = self._to_read(row)
        areas, summary = derive_focus_areas(
            questions=read.questions,
            answers=read.answers,
            timed_out=timed_out,
        )
        return DiagnosticResultRead(
            diagnostic=read,
            focus_areas=areas,
            timed_out=timed_out,
            coaching_summary=summary,
        )

    async def get(self, *, diagnostic_id: str) -> DiagnosticRead:
        row = await self._repo.get_by_id(diagnostic_id)
        if row is None:
            raise PreconditionFailedError("Diagnostic not found or expired")
        now = _utcnow()
        if row.status == DiagnosticStatus.IN_PROGRESS and self._is_expired(row, now):
            # Surface as still readable so FE can call finalize-timeout.
            return self._to_read(row)
        return self._to_read(row)

    async def start_with_generated_questions(
        self,
        *,
        student_user_id: str,
        subject_id: str | None = None,
        framework_id: str | None = None,
        target_language: Literal["en", "ur", "sd", "ps"] = "en",
        grade_label: str = "",
        subject_name: str = "",
        framework_name: str = "",
        context_json: dict[str, Any] | None = None,
        question_count: int = 20,
    ) -> DiagnosticRead:
        """Generate 15–25 questions (bank hook / LLM) then start the attempt (T-104)."""
        self._validate_scope(subject_id, framework_id)
        tenant_kind: Literal["school", "independent"] = (
            "independent" if self._tenant_type == "independent" else "school"
        )
        questions = await generate_diagnostic_questions(
            tenant_kind=tenant_kind,
            target_language=target_language,
            grade_label=grade_label,
            subject_name=subject_name,
            subject_id=subject_id,
            framework_name=framework_name,
            framework_id=framework_id,
            context_json=context_json,
            question_count=question_count,
        )
        return await self.start(
            student_user_id=student_user_id,
            subject_id=subject_id,
            framework_id=framework_id,
            questions=questions,
        )
