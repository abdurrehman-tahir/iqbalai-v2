"""M-08 Mode + Diagnostic + Cognitive DNA milestone E2E smoke — T-111.

Drives mode toggle + diagnostic lifecycle through the real service layer against
in-memory fakes (no live DB, no live LLM network — CI-safe). Covers:

- school mode switch with no data loss + independent 404
- school per-subject diagnostic: start → save → resume → complete → DNA in school schema
- independent per-framework diagnostic → DNA in independent schema
- retake within 30 days blocked
- exam-date 30-day countdown (time-warped)
- coaching-only results (never a grade)
- M-08 audit actions registered

Side effects (NATS / notifications / audit writes) are stubbed; covered by feature tests.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import NotFoundError, PreconditionFailedError
from app.features.audit.actions import (
    COGNITIVE_DNA_SEEDED,
    DIAGNOSTIC_COMPLETED,
    DIAGNOSTIC_RETAKEN,
    DIAGNOSTIC_STARTED,
    M08_AUDIT_ACTIONS,
    REGISTERED_AUDIT_ACTIONS,
    STUDENT_MODE_CHANGED,
)
from app.features.cognitive_dna.models import IndependentCognitiveDna, SchoolCognitiveDna
from app.features.diagnostics.models import IndependentDiagnostic, SchoolDiagnostic
from app.features.diagnostics.service import (
    RETAKE_BLOCKED_MESSAGE,
    RETAKE_COOLDOWN,
    DiagnosticService,
)
from app.features.diagnostics.tests.test_diagnostic_lifecycle import _FakeDnaRepo, _FakeRepo
from app.features.student_mode.models import StudyMode, UserSettings
from app.features.student_mode.schemas import StudentModeUpdate
from app.features.student_mode.service import StudentModeService
from app.features.student_onboarding.models import StudentProfile
from app.features.student_onboarding.service import (
    EXAM_COUNTDOWN_DAYS,
    StudentOnboardingService,
)
from app.features.users.models import User, UserAccountStatus, UserRole

SCHOOL_STUDENT = User(
    id="stu-m08",
    authentik_id="auth-stu-m08",
    email="stu-m08@example.com",
    display_name="M08 Student",
    role=UserRole.STUDENT,
    status=UserAccountStatus.ACTIVE,
    school_id="school-1",
)

SCHOOL_CLAIMS: dict[str, object] = {
    "sub": "auth-stu-m08",
    "role": "student",
    "tenant_type": "school",
}

INDEPENDENT_CLAIMS: dict[str, object] = {
    "sub": "auth-ind-m08",
    "role": "independent_student",
    "tenant_type": "independent",
}

_GRADE_KEYS = frozenset({"score", "percentage", "grade", "percent", "mark", "marks"})


class _ModeSettingsRepo:
    store: dict[str, UserSettings] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_user_id(self, user_id: str) -> UserSettings | None:
        return self.store.get(user_id)

    async def create(self, settings: UserSettings) -> UserSettings:
        self.store[settings.user_id] = settings
        return settings

    async def update(self, settings: UserSettings) -> UserSettings:
        self.store[settings.user_id] = settings
        return settings


class _ModeProfileRepo:
    store: dict[str, StudentProfile] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_user_id(self, user_id: str) -> StudentProfile | None:
        return self.store.get(user_id)

    async def update(self, profile: StudentProfile) -> StudentProfile:
        self.store[profile.user_id] = profile
        return profile

    async def list_with_exam_dates(self) -> list[StudentProfile]:
        return [p for p in self.store.values() if p.exam_date is not None]


class _ModeUserRepo:
    store: dict[str, User] = {}

    def __init__(self, session: Any) -> None:
        pass

    async def get_by_authentik_id(self, authentik_id: str) -> User | None:
        return next((u for u in self.store.values() if u.authentik_id == authentik_id), None)

    async def get_by_id(self, user_id: str) -> User | None:
        return self.store.get(user_id)


def _assert_no_grade(payload: dict[str, Any]) -> None:
    """Results must stay coaching-only — never expose a grade/score (Flow 4 §3.6)."""
    for key in payload:
        assert key not in _GRADE_KEYS, f"grade-like field present: {key}"
    summary = str(payload.get("coaching_summary", ""))
    assert "%" not in summary
    assert "failed" not in summary.lower()
    for area in payload.get("focus_areas", []):
        if isinstance(area, dict):
            for key in area:
                assert key not in _GRADE_KEYS


@pytest.fixture(autouse=True)
def _patch_m08(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeRepo.store = {}
    _FakeDnaRepo.store = {}
    profile = StudentProfile(
        user_id=SCHOOL_STUDENT.id,
        display_name="M08 Student",
        language_preference="en",
        tos_accepted_at=datetime.now(timezone.utc),
        profile_basic_completed_at=datetime.now(timezone.utc),
        lecture_mode_enabled=True,
        self_study_mode_enabled=True,
    )
    _ModeSettingsRepo.store = {}
    _ModeProfileRepo.store = {SCHOOL_STUDENT.id: profile}
    _ModeUserRepo.store = {SCHOOL_STUDENT.id: SCHOOL_STUDENT}

    monkeypatch.setattr("app.features.diagnostics.service.DiagnosticRepository", _FakeRepo)
    monkeypatch.setattr("app.features.diagnostics.service.CognitiveDnaRepository", _FakeDnaRepo)
    monkeypatch.setattr(
        "app.features.diagnostics.service.publish_diagnostic_completed",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "app.features.diagnostics.service.DiagnosticService._notify_completed",
        AsyncMock(),
    )
    monkeypatch.setattr("app.features.diagnostics.service.audit", AsyncMock())
    monkeypatch.setattr(
        "app.features.diagnostics.service.DiagnosticService._audit_lifecycle",
        AsyncMock(),
    )

    monkeypatch.setattr(
        "app.features.student_mode.service.UserSettingsRepository", _ModeSettingsRepo
    )
    monkeypatch.setattr(
        "app.features.student_mode.service.StudentProfileRepository", _ModeProfileRepo
    )
    monkeypatch.setattr("app.features.student_mode.service.UserRepository", _ModeUserRepo)
    monkeypatch.setattr("app.features.student_mode.service.audit", AsyncMock())
    monkeypatch.setattr("app.features.student_mode.service.publish_mode_changed", AsyncMock())

    monkeypatch.setattr(
        "app.features.student_onboarding.service.StudentProfileRepository", _ModeProfileRepo
    )
    monkeypatch.setattr("app.features.student_onboarding.service.UserRepository", _ModeUserRepo)
    monkeypatch.setattr("app.features.student_onboarding.service.audit", AsyncMock())
    monkeypatch.setattr(
        "app.features.student_onboarding.service.StudentOnboardingService._active_enrollment_grade_id",
        AsyncMock(return_value="grade-9"),
    )

    class _EmptyLinks:
        def __init__(self, session: Any) -> None:
            pass

        async def list_approved_for_student(self, student_user_id: str) -> list[Any]:
            return []

    monkeypatch.setattr(
        "app.features.student_onboarding.service.ParentChildLinkRepository",
        _EmptyLinks,
    )


def test_m08_audit_actions_registered() -> None:
    for action in (
        STUDENT_MODE_CHANGED,
        DIAGNOSTIC_STARTED,
        DIAGNOSTIC_COMPLETED,
        DIAGNOSTIC_RETAKEN,
        COGNITIVE_DNA_SEEDED,
    ):
        assert action in M08_AUDIT_ACTIONS
        assert action in REGISTERED_AUDIT_ACTIONS


def test_m08_schema_isolation() -> None:
    assert SchoolDiagnostic.__table__.schema == "school"
    assert IndependentDiagnostic.__table__.schema == "independent"
    assert SchoolCognitiveDna.__table__.schema == "school"
    assert IndependentCognitiveDna.__table__.schema == "independent"
    assert SchoolDiagnostic.__tablename__ == "diagnostics"
    assert SchoolCognitiveDna.__tablename__ == "cognitive_dna"


@pytest.mark.asyncio
async def test_m08_mode_diagnostic_dna_e2e(monkeypatch: pytest.MonkeyPatch) -> None:
    session: Any = AsyncMock()
    mode_svc = StudentModeService(session)

    # --- Mode: school toggle preserves leaving-mode state (no data loss) ---
    initial = await mode_svc.get_mode(SCHOOL_CLAIMS)
    assert initial.active_mode == "lecture"
    assert initial.mode_state.lecture == {}
    assert initial.mode_state.self_study == {}

    switched = await mode_svc.set_mode(
        StudentModeUpdate(
            active_mode="self_study",
            leaving_mode_state={"scroll_y": 240, "section": "lectures"},
        ),
        SCHOOL_CLAIMS,
        actor_id=SCHOOL_STUDENT.id,
    )
    assert switched.active_mode == "self_study"
    assert switched.mode_state.lecture == {"scroll_y": 240, "section": "lectures"}
    assert switched.mode_state.self_study == {}

    back = await mode_svc.set_mode(
        StudentModeUpdate(
            active_mode="lecture",
            leaving_mode_state={"topic": "kinematics"},
        ),
        SCHOOL_CLAIMS,
        actor_id=SCHOOL_STUDENT.id,
    )
    assert back.active_mode == "lecture"
    assert back.mode_state.lecture == {"scroll_y": 240, "section": "lectures"}
    assert back.mode_state.self_study == {"topic": "kinematics"}
    assert _ModeSettingsRepo.store[SCHOOL_STUDENT.id].active_mode is StudyMode.LECTURE

    # --- Mode: independent students get 404 (no switcher) ---
    with pytest.raises(NotFoundError, match="Mode switcher is not available"):
        await mode_svc.get_mode(INDEPENDENT_CLAIMS)
    with pytest.raises(NotFoundError, match="Mode switcher is not available"):
        await mode_svc.set_mode(
            StudentModeUpdate(active_mode="self_study"),
            INDEPENDENT_CLAIMS,
            actor_id="ind-m08",
        )

    # --- School diagnostic: start → save → resume → complete → DNA (school + subject) ---
    school_diag = DiagnosticService(session=session, tenant_type="school")
    questions = [
        {"id": "q1", "prompt": "Force?", "choices": ["A", "B"], "topic": "Newton's Laws"},
        {"id": "q2", "prompt": "Lens?", "choices": ["A", "B"], "topic": "Optics"},
    ]
    started = await school_diag.start(
        student_user_id=SCHOOL_STUDENT.id,
        subject_id="subj-physics",
        questions=questions,
    )
    assert started.status == "in_progress"
    assert started.subject_id == "subj-physics"
    assert started.framework_id is None
    assert started.tenant_type == "school"

    saved = await school_diag.save_answers(diagnostic_id=started.id, answers={"q1": "A", "q2": "B"})
    assert saved.answers == {"q1": "A", "q2": "B"}

    resumed = await school_diag.resume(diagnostic_id=started.id)
    assert resumed.id == started.id
    assert resumed.answers == {"q1": "A", "q2": "B"}

    school_result = await school_diag.complete(diagnostic_id=started.id)
    assert school_result.diagnostic.status == "completed"
    assert school_result.focus_areas
    result_dump = school_result.model_dump()
    _assert_no_grade(result_dump)
    for area in school_result.focus_areas:
        assert set(area.model_dump()) == {"topic", "suggestion"}

    school_dna_key = f"{SCHOOL_STUDENT.id}:subj-physics:None"
    school_dna = _FakeDnaRepo.store[school_dna_key]
    assert school_dna["tenant_type"] == "school"
    assert school_dna["subject_id"] == "subj-physics"
    assert school_dna["framework_id"] is None
    assert school_dna["focus_areas_jsonb"]

    # --- Retake within 30 days blocked ---
    with pytest.raises(PreconditionFailedError) as blocked:
        await school_diag.start(student_user_id=SCHOOL_STUDENT.id, subject_id="subj-physics")
    assert RETAKE_BLOCKED_MESSAGE in str(blocked.value)

    # After cooldown, retake is allowed (time-warped completed_at).
    _FakeRepo.store[started.id].completed_at = (
        datetime.now(timezone.utc) - RETAKE_COOLDOWN - timedelta(hours=1)
    )
    retake = await school_diag.start(
        student_user_id=SCHOOL_STUDENT.id,
        subject_id="subj-physics",
        questions=questions,
    )
    assert retake.id != started.id
    assert retake.status == "in_progress"

    # --- Independent diagnostic → DNA in independent schema (framework-scoped) ---
    ind_diag = DiagnosticService(session=session, tenant_type="independent")
    ind_started = await ind_diag.start(
        student_user_id="ind-m08",
        framework_id="fw-matric",
        questions=questions,
    )
    assert ind_started.tenant_type == "independent"
    assert ind_started.framework_id == "fw-matric"
    assert ind_started.subject_id is None
    await ind_diag.save_answers(diagnostic_id=ind_started.id, answers={"q1": "A"})
    ind_result = await ind_diag.complete(diagnostic_id=ind_started.id)
    _assert_no_grade(ind_result.model_dump())

    ind_dna = _FakeDnaRepo.store["ind-m08:None:fw-matric"]
    assert ind_dna["tenant_type"] == "independent"
    assert ind_dna["framework_id"] == "fw-matric"
    assert ind_dna["subject_id"] is None

    # --- Exam-date 30-day countdown (time-warped) ---
    profile = _ModeProfileRepo.store[SCHOOL_STUDENT.id]
    profile.exam_date = date.today() + timedelta(days=30)
    profile.exam_countdown_sent_days = None
    notify_mock = AsyncMock()
    monkeypatch.setattr(
        "app.infrastructure.notifications.self_study.notify_self_study_event",
        notify_mock,
    )
    onboarding = StudentOnboardingService(session)
    countdown_count = await onboarding.send_exam_countdown_notifications()
    assert countdown_count == 1
    assert profile.exam_countdown_sent_days == "30"
    assert 30 in EXAM_COUNTDOWN_DAYS
    notify_mock.assert_called_once()
