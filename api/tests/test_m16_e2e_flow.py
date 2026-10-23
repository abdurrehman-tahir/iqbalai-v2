"""T-208 — M-16 milestone E2E: the full Flow 7 next-day review loop.

Real services against real Postgres (DB_URL, as CI provides); only external
boundaries are mocked — the LLM (criticality / summary / reflective / scoring),
BGE-M3 embeddings, Pattern-S generation internals, the vector originality index,
NATS and notification delivery. Celery is "time-warped" by calling each task's
async body directly with explicit Karachi timestamps. No live network.

Journey (numbers match the T-208 acceptance list):
 2  a day of questions → aggregate (#72 opt-out excluded) → cosine cluster →
    classify (frequency + criticality) → one cluster fails → DLQ, review ships
 3  mini-lectures generated (lecture_type=mini, web fallback off, cost cap) and
    scored (Depth/Alignment ×1.5, max 60)
 4  card assembled; 05:00 SLA met; nothing sent at 05:59, one notify at 06:00;
    student names teacher-only; reply + skip; targeted publish to the triggering,
    still-enrolled students only (no auto-quiz, cross-grade link blocked);
    other-school staff get 404 (§3.13); the review sits on the lecture's Reviews tab
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.features.grades.models import Grade
from app.features.lectures import scoring
from app.features.lectures.models import (
    LectureStatus,
    LectureType,
    SchoolLecture,
    SchoolLectureAssignment,
    SchoolLectureVersion,
)
from app.features.lectures.originality import OriginalityResult
from app.features.lectures.schemas import LectureLinkCreate
from app.features.lectures.service import LectureWizardService
from app.features.next_day_review import (
    assembly,
    classification,
    clustering,
    distribution,
    mini_generation,
    reflection,
)
from app.features.next_day_review import service as review_service_mod
from app.features.next_day_review.aggregation import KARACHI, aggregate_school_day
from app.features.next_day_review.assembly import assemble_reviews, check_sla, notify_ready_reviews
from app.features.next_day_review.classification import classify_clusters
from app.features.next_day_review.clustering import cluster_all_buckets
from app.features.next_day_review.mini_generation import generate_minis_for_qualifying
from app.features.next_day_review.models import (
    LectureReview,
    LectureReviewStatus,
    ReviewClassificationFailure,
    ReviewReply,
    SkippedCluster,
)
from app.features.next_day_review.schemas import ReviewReplyCreate
from app.features.next_day_review.service import NextDayReviewService
from app.features.offerings.models import GradeSubjectOffering
from app.features.quizzes.generation import enqueue_quiz_generation_for_lecture
from app.features.schools.models import District, School
from app.features.sections.models import Section
from app.features.student_enrollments.models import StudentEnrollment, StudentEnrollmentStatus
from app.features.student_events.models import SchoolStudentEvent, StudentEventTenantType
from app.features.student_highlights.tests.pg_support import make_user, requires_pg
from app.features.subjects.models import Subject
from app.features.users.models import User, UserRole

pytestmark = requires_pg

REVIEW_DATE = date(2026, 10, 22)
SESSION = "2026-2027"
MINI_BODY = " ".join(["Action and reaction act on different bodies."] * 120)  # ~840 words
CANCEL_Q = "Why don't action and reaction forces cancel out?"
SMALLER_Q = "Is the reaction force smaller than the action force?"
INERTIA_Q = "What exactly is inertia?"


def _claims(user: User) -> dict[str, object]:
    return {"sub": user.authentik_id, "role": user.role.value, "school_id": user.school_id}


async def _seed(pg: AsyncSession) -> dict[str, Any]:
    district = District(name="M16 District")
    pg.add(district)
    await pg.flush()
    school = School(name="M16 School", district_id=district.id)
    pg.add(school)
    await pg.flush()
    grade = Grade(school_id=school.id, name="Grade 9", academic_session=SESSION, level_ordinal=9)
    pg.add(grade)
    await pg.flush()
    section = Section(grade_id=grade.id, name="9-A")
    subject = Subject(school_id=school.id, name="Physics", language="en")
    pg.add_all([section, subject])
    await pg.flush()
    gso = GradeSubjectOffering(
        school_id=school.id, grade_id=grade.id, subject_id=subject.id, academic_session=SESSION
    )
    pg.add(gso)
    await pg.flush()

    teacher = await make_user(pg, role=UserRole.TEACHER, school_id=school.id)
    coordinator = await make_user(pg, role=UserRole.COORDINATOR, school_id=school.id)
    # 5 askers + 3 silent classmates: roster 7 active, so one asker (14%) stays
    # below the 25% roster frequency rule.
    students = [await make_user(pg, role=UserRole.STUDENT, school_id=school.id) for _ in range(8)]
    for i, student in enumerate(students):
        pg.add(
            StudentEnrollment(
                school_id=school.id,
                student_user_id=student.id,
                grade_id=grade.id,
                section_id=section.id,
                academic_session=SESSION,
                # stu 3 transferred out before publish → dropped from recipients (§5.4).
                status=(
                    StudentEnrollmentStatus.WITHDRAWN if i == 3 else StudentEnrollmentStatus.ACTIVE
                ),
                enrolled_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
            )
        )
    lecture = SchoolLecture(
        school_id=school.id,
        grade_subject_offering_id=gso.id,
        teacher_user_id=teacher.id,
        title="Newton's Laws",
        topic="Newton's third law",
        status=LectureStatus.PUBLISHED,
    )
    pg.add(lecture)
    await pg.flush()

    def _ask(student: User, para: str, text: str, minute: int, *, private: bool = False) -> None:
        payload: dict[str, object] = {
            "question_id": f"q-{student.id[-6:]}-{para}",
            "question_text": text,
            "paragraph_id": para,
            "source_chunk_id": f"chunk-{para}",
            "teacher_share": "private" if private else "share",
        }
        pg.add(
            SchoolStudentEvent(
                tenant_type=StudentEventTenantType.SCHOOL,
                tenant_id=school.id,
                user_id=student.id,
                lecture_id=lecture.id,
                event_type="student.question.asked",
                event_payload_jsonb=payload,
                occurred_at=datetime(2026, 10, 22, 10, minute, tzinfo=KARACHI),
            )
        )

    for i in range(4):
        _ask(students[i], "p1", CANCEL_Q, i)
    # #72: this student opted out of sharing — must never reach the teacher.
    _ask(students[4], "p1", CANCEL_Q, 9, private=True)
    for i, student in enumerate([students[0], students[1], students[4]]):
        _ask(student, "p2", SMALLER_Q, 20 + i)
    _ask(students[2], "p3", INERTIA_Q, 40)
    await pg.flush()
    return {
        "school": school,
        "gso": gso,
        "teacher": teacher,
        "coordinator": coordinator,
        "students": students,
        "lecture": lecture,
    }


@pytest.fixture
def boundaries(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Mock ONLY external boundaries; every M-16 code path runs for real."""
    captured: dict[str, Any] = {"events": [], "teacher_notified": [], "students_notified": []}

    async def _embed(texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0, 0.0] for _ in texts]  # one cosine cluster per bucket

    async def _criticality(messages: list[dict[str, str]], **_: Any) -> str:
        user = messages[1]["content"]
        if INERTIA_Q in user:
            raise TimeoutError("llm timeout")  # → DLQ
        score = 8 if CANCEL_Q in user else 3
        return f'{{"criticality": {score}, "rationale": "r"}}'

    async def _generate(session: AsyncSession, **kw: Any) -> str:
        assert kw["allow_web_fallback"] is False  # T-198: web fallback off for minis
        version = SchoolLectureVersion(lecture_id=kw["lecture_id"], version=1, body=MINI_BODY)
        session.add(version)
        await session.flush()
        mini = await session.get(SchoolLecture, kw["lecture_id"])
        assert mini is not None
        mini.current_version_id = version.id
        mini.status = LectureStatus.READY_FOR_EDIT
        await session.flush()
        return version.id

    async def _event(**kw: Any) -> None:
        captured["events"].append(kw["event_type"])

    async def _teacher_notify(**kw: Any) -> None:
        captured["teacher_notified"].append(kw["template_key"])

    async def _student_notify(**kw: Any) -> None:
        captured["students_notified"].append(kw["recipient_user_id"])

    monkeypatch.setattr(clustering, "embed", _embed)
    monkeypatch.setattr(classification, "chat", _criticality)
    monkeypatch.setattr(mini_generation, "run_lecture_generation", _generate)
    monkeypatch.setattr(
        mini_generation, "_resolve_library_ids", AsyncMock(return_value=("curriculum-1", []))
    )
    monkeypatch.setattr(mini_generation, "publish_lecture_event", _event)
    monkeypatch.setattr(
        assembly, "chat", AsyncMock(return_value='{"summary": "Students mixed up force pairs."}')
    )
    monkeypatch.setattr(
        reflection,
        "chat",
        AsyncMock(return_value='{"question": "Could a tug-of-war demo make the pair concrete?"}'),
    )
    monkeypatch.setattr(assembly, "notify_lecture_event", _teacher_notify)
    monkeypatch.setattr(assembly, "_resolve_recipient", AsyncMock(return_value=("ak", "en")))
    monkeypatch.setattr(assembly, "notify_all_platform_admins", AsyncMock())
    monkeypatch.setattr(review_service_mod, "publish_lecture_event", _event)
    monkeypatch.setattr(distribution, "notify_lecture_event", _student_notify)
    # Scoring boundaries: LLM + vector index + embeddings + teacher-facing notify.
    monkeypatch.setattr(
        scoring,
        "chat",
        AsyncMock(
            return_value=(
                '{"originality": 7, "depth": 8, "cultural_relevance": 4, "engagement": 3, '
                '"alignment": 9, "voice_quality": 4, "ai_learning": 6}'
            )
        ),
    )
    monkeypatch.setattr(
        scoring,
        "check_and_index_school_originality",
        AsyncMock(
            return_value=OriginalityResult(
                originality_score=Decimal("0.900"),
                max_similarity=0.1,
                is_flagged=False,
                matched_version_id=None,
            )
        ),
    )
    monkeypatch.setattr(scoring, "compute_topic_relevance", AsyncMock(return_value=None))
    monkeypatch.setattr(scoring, "detect_and_track_weakness_school", AsyncMock())
    monkeypatch.setattr(scoring, "notify_scoring_complete", AsyncMock())
    return captured


async def test_m16_full_flow(pg: AsyncSession, boundaries: dict[str, Any]) -> None:
    seed = await _seed(pg)
    school, lecture, students = seed["school"], seed["lecture"], seed["students"]
    teacher, coordinator = seed["teacher"], seed["coordinator"]

    # --- #2 overnight pipeline (time-warped: the 23:00 beat body, run directly) ---
    buckets = await aggregate_school_day(pg, school.id, REVIEW_DATE)
    all_users = {item["user_id"] for items in buckets.values() for item in items}
    assert students[4].id not in {
        i["user_id"] for i in buckets[next(k for k in buckets if "|p1|" in k)]
    }, "#72 opt-out leaked"
    assert students[4].id in all_users  # ...but their shared p2 question still counts

    clusters = await cluster_all_buckets(buckets)
    classified = await classify_clusters(pg, school_id=school.id, clusters=clusters)
    assert classified.dlq_written == 1
    dlq = (await pg.execute(select(ReviewClassificationFailure))).scalars().all()
    assert [d.school_id for d in dlq] == [school.id]
    assert len(classified.qualifying) == 2  # p1 (critical) + p2 (frequency); p3 not

    # --- #3 mini-lectures: generated with mini flags, then scored ×1.5 / 60 ---
    minis = await generate_minis_for_qualifying(
        pg, school_id=school.id, clusters=classified.qualifying
    )
    assert [m["status"] for m in minis] == ["generated", "generated"]
    assert boundaries["events"].count("mini_lecture.generated") == 2
    mini_ids = [m["lecture_id"] for m in minis]
    for mini_id in mini_ids:
        mini = await pg.get(SchoolLecture, mini_id)
        assert mini is not None
        assert mini.lecture_type == LectureType.MINI
        assert mini.parent_lecture_id == lecture.id
    assert mini_generation.estimate_mini_cost_usd(len(MINI_BODY.split())) < 0.50

    first_mini = await pg.get(SchoolLecture, mini_ids[0])
    assert first_mini is not None and first_mini.current_version_id is not None
    await scoring.score_school_lecture_version(
        pg, lecture_id=first_mini.id, school_id=school.id, version_id=first_mini.current_version_id
    )
    scored = await pg.get(SchoolLectureVersion, first_mini.current_version_id)
    assert scored is not None and scored.scores_jsonb is not None
    assert scored.scores_jsonb["depth"] == 12 and scored.scores_jsonb["alignment"] == 14
    assert scored.scores_jsonb["max"] == 60

    # --- #4 card assembly + 05:00 SLA + 06:00 notify ---
    reviews = await assemble_reviews(
        pg, school_id=school.id, review_date=REVIEW_DATE, clusters=classified.clusters, minis=minis
    )
    assert len(reviews) == 1
    review = reviews[0]
    assert review.lecture_id == lecture.id
    assert review.ai_summary == "Students mixed up force pairs."
    assert review.reflective_prompt.startswith("Could a tug-of-war")
    assert review.pending_action is True
    assert {c["column"] for c in review.clusters_jsonb} == {"critical", "high_frequency"}

    assert await check_sla(pg, review_date=REVIEW_DATE) == []
    too_early = datetime(2026, 10, 23, 5, 59, tzinfo=KARACHI)
    assert await notify_ready_reviews(pg, review_date=REVIEW_DATE, now=too_early) == 0
    at_six = datetime(2026, 10, 23, 6, 0, tzinfo=KARACHI)
    assert await notify_ready_reviews(pg, review_date=REVIEW_DATE, now=at_six) == 1
    assert await notify_ready_reviews(pg, review_date=REVIEW_DATE, now=at_six) == 0  # once
    assert boundaries["teacher_notified"] == ["lectures.next_day_review_ready"]

    # --- names teacher-only; coordinator aggregate-only ---
    svc = NextDayReviewService(pg)
    teacher_view = await svc.get_review(_claims(teacher), review.id)
    names = {q.student_name for c in teacher_view.critical for q in c.questions}
    assert None not in names and len(names) == 4
    coord_view = await svc.get_review(_claims(coordinator), review.id)
    assert all(q.student_name is None for c in coord_view.critical for q in c.questions)
    assert coord_view.can_act is False

    # --- reply + skip ---
    critical = teacher_view.critical[0]
    frequent = teacher_view.high_frequency[0]
    await svc.reply(
        _claims(teacher),
        review.id,
        ReviewReplyCreate(
            cluster_ref=critical.cluster_ref,
            student_user_id=students[0].id,
            body="They act on different bodies — see the diagram.",
        ),
    )
    await svc.skip(_claims(teacher), review.id, frequent.cluster_ref)
    assert len((await pg.execute(select(ReviewReply))).scalars().all()) == 1
    assert [s.cluster_ref for s in (await pg.execute(select(SkippedCluster))).scalars().all()] == [
        frequent.cluster_ref
    ]

    # --- targeted publish: triggering + still-enrolled only ---
    detail = await svc.publish_mini(_claims(teacher), review.id)
    assert detail.mini_published is True
    rows = (
        (
            await pg.execute(
                select(SchoolLectureAssignment).where(
                    SchoolLectureAssignment.lecture_id == review.mini_lecture_id
                )
            )
        )
        .scalars()
        .all()
    )
    recipients = {r.student_user_id for r in rows}
    # p1 askers were stu 0-3; stu 3 withdrew, stu 4 opted out → exactly 0, 1, 2.
    assert recipients == {students[0].id, students[1].id, students[2].id}
    assert len(boundaries["students_notified"]) == 3
    assert "mini_lecture.assigned" in boundaries["events"]
    refreshed = await pg.get(LectureReview, review.id)
    assert refreshed is not None and refreshed.status == LectureReviewStatus.COMPLETED

    published_mini = await pg.get(SchoolLecture, review.mini_lecture_id)
    assert published_mini is not None
    assert await enqueue_quiz_generation_for_lecture(pg, lecture=published_mini) == 0
    wizard = LectureWizardService(pg)
    with pytest.raises(ValidationError):
        await wizard.link_lecture(
            _claims(teacher),
            published_mini.id,
            LectureLinkCreate(target_grade_subject_offering_id=seed["gso"].id),
        )

    # --- §3.13 cross-tenant denial: another school's staff gets 404, list is empty ---
    other_school = School(name="M16 Other School", district_id=school.district_id)
    pg.add(other_school)
    await pg.flush()
    outsider_admin = await make_user(pg, role=UserRole.SCHOOL_ADMIN, school_id=other_school.id)
    outsider_teacher = await make_user(pg, role=UserRole.TEACHER, school_id=other_school.id)
    for outsider in (outsider_admin, outsider_teacher):
        with pytest.raises(NotFoundError):
            await svc.get_review(_claims(outsider), review.id)
        assert await svc.list_reviews(_claims(outsider)) == []

    # --- the review is a child record on the lecture's Reviews tab ---
    tab = await svc.list_reviews(_claims(teacher), lecture_id=lecture.id)
    assert [r.id for r in tab] == [review.id]
