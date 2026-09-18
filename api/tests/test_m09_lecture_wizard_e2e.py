"""M-09 Lecture Wizard + AI Generation milestone E2E smoke test — T-127.

Drives the full lecture-wizard lifecycle through the real service layer against
shared in-memory stores (no live DB, no live network — the LLM and SearXNG are
replaced with fixture responses, so this runs in CI): teacher lists
offerings/curricula/topics -> Step 3 references -> draft auto-saves and resumes
-> Step 5 commits (GENERATING) -> the real dual-RAG pipeline runs (LLM mocked)
and persists paragraphs tagged with curriculum/reference source badges ->
out-of-curriculum fallback escalates to a mocked web search -> cross-grade
linking is allowed downward and blocked upward -> per-lecture access
restriction is enforced -> the independent-teacher stripped variant runs its
own (school-library-free) version of the same generate + source-badge flow.

Notifications + audit (T-126) are post-commit best-effort/synchronous side
effects and are stubbed here; they're covered by test_lecture_notifications.py
and the audit assertions in the wizard/links/access test files.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import PermissionDeniedError
from app.features.grades.models import Grade, GradeStatus
from app.features.independent_users.models import (
    IndependentUser,
    IndependentUserAccountStatus,
    IndependentUserRole,
)
from app.features.lectures import generation as generation_mod
from app.features.lectures import independent_generation as independent_generation_mod
from app.features.lectures import independent_service as independent_service_mod
from app.features.lectures import service as service_mod
from app.features.lectures.generation import run_lecture_generation
from app.features.lectures.independent_generation import run_independent_lecture_generation
from app.features.lectures.independent_service import IndependentLectureWizardService
from app.features.lectures.models import (
    IndependentLecture,
    IndependentLectureDraft,
    IndependentLectureParagraph,
    LectureStatus,
    LectureType,
    SchoolLecture,
    SchoolLectureAssignment,
    SchoolLectureDraft,
    SchoolLectureLink,
    SchoolLectureParagraph,
    SchoolLectureVersion,
)
from app.features.lectures.schemas import (
    IndependentLectureGenerateRequest,
    LectureAccessSettingsUpdate,
    LectureAssignmentInput,
    LectureAssignmentScope,
    LectureDraftUpsert,
    LectureGenerateRequest,
    LectureLinkCreate,
    TeachingMode,
)
from app.features.lectures.service import LectureWizardService
from app.features.library.independent_personal_models import (
    IndependentPersonalContent,
    PersonalContentStatus,
    PersonalContentType,
)
from app.features.library.school_models import (
    LibraryContentType,
    LibraryIngestionStatus,
    LibraryVisibility,
    SchoolLibraryItem,
)
from app.features.offerings.models import GradeSubjectOffering, OfferingStatus
from app.features.sections.models import Section, SectionStatus
from app.features.student_enrollments.models import StudentEnrollment, StudentEnrollmentStatus
from app.features.subjects.models import Subject, SubjectStatus
from app.features.teacher_onboarding.models import TeacherProfile
from app.features.users.models import User, UserAccountStatus, UserRole
from app.infrastructure.rag.web_search import SearchResult

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

# --- fixtures: one consistent school scenario across the whole flow ---------

TEACHER = User(
    id="teacher-1",
    authentik_id="auth-teacher",
    email="teacher@example.com",
    display_name="Teacher One",
    role=UserRole.TEACHER,
    status=UserAccountStatus.ACTIVE,
    school_id="school-1",
)

GRADE_9 = Grade(
    id="grade-9",
    school_id="school-1",
    name="Grade 9",
    academic_session="2025-2026",
    level_ordinal=9,
    status=GradeStatus.ACTIVE,
)
GRADE_10 = Grade(
    id="grade-10",
    school_id="school-1",
    name="Grade 10",
    academic_session="2025-2026",
    level_ordinal=10,
    status=GradeStatus.ACTIVE,
)

SUBJECT = Subject(
    id="subj-physics",
    school_id="school-1",
    name="Physics",
    language="en",
    status=SubjectStatus.ACTIVE,
)

# Teacher owns both — required for the self-link acceptance case.
OFFERING_G9 = GradeSubjectOffering(
    id="off-g9",
    school_id="school-1",
    grade_id="grade-9",
    subject_id="subj-physics",
    assigned_teacher_id="teacher-1",
    academic_session="2025-2026",
    status=OfferingStatus.ACTIVE,
)
OFFERING_G10 = GradeSubjectOffering(
    id="off-g10",
    school_id="school-1",
    grade_id="grade-10",
    subject_id="subj-physics",
    assigned_teacher_id="teacher-1",
    academic_session="2025-2026",
    status=OfferingStatus.ACTIVE,
)

CURRICULUM = SchoolLibraryItem(
    id="curr-1",
    school_id="school-1",
    title="Punjab Physics 9-10",
    content_type=LibraryContentType.CURRICULUM,
    language="en",
    subject_id="subj-physics",
    grade_level_ordinal=9,
    storage_key="k1",
    sha256="a" * 64,
    ingestion_status=LibraryIngestionStatus.AVAILABLE,
    topic_tree_jsonb={"chapters": [{"title": "Mechanics"}], "parse_degraded": False},
    created_by="teacher-1",
    visibility=LibraryVisibility.SCHOOL_PUBLIC,
)
REFERENCE = SchoolLibraryItem(
    id="ref-1",
    school_id="school-1",
    title="Grade 9 Physics Reference",
    content_type=LibraryContentType.REFERENCE,
    language="en",
    subject_id="subj-physics",
    grade_level_ordinal=9,
    storage_key="k2",
    sha256="b" * 64,
    ingestion_status=LibraryIngestionStatus.AVAILABLE,
    topic_tree_jsonb=None,
    created_by="teacher-1",
    visibility=LibraryVisibility.SCHOOL_PUBLIC,
)

PROFILE = TeacherProfile(user_id="teacher-1", name="Teacher One", language_preference="en")

SECTION_A = Section(id="section-a", grade_id="grade-9", name="A", status=SectionStatus.ACTIVE)
SECTION_B = Section(id="section-b", grade_id="grade-9", name="B", status=SectionStatus.ACTIVE)

STUDENT_1 = User(
    id="student-1",
    authentik_id="auth-student-1",
    email="s1@example.com",
    display_name="Student One",
    role=UserRole.STUDENT,
    status=UserAccountStatus.ACTIVE,
    school_id="school-1",
)
STUDENT_2 = User(
    id="student-2",
    authentik_id="auth-student-2",
    email="s2@example.com",
    display_name="Student Two",
    role=UserRole.STUDENT,
    status=UserAccountStatus.ACTIVE,
    school_id="school-1",
)
ENROLLMENT_1 = StudentEnrollment(
    id="enr-1",
    school_id="school-1",
    student_user_id="student-1",
    grade_id="grade-9",
    section_id="section-a",
    academic_session="2025-2026",
    status=StudentEnrollmentStatus.ACTIVE,
    enrolled_at=datetime.now(timezone.utc),
)
ENROLLMENT_2 = StudentEnrollment(
    id="enr-2",
    school_id="school-1",
    student_user_id="student-2",
    grade_id="grade-9",
    section_id="section-b",
    academic_session="2025-2026",
    status=StudentEnrollmentStatus.ACTIVE,
    enrolled_at=datetime.now(timezone.utc),
)

# --- fixtures: independent teacher scenario ----------------------------------

IND_TEACHER = IndependentUser(
    id="ind-teacher-1",
    authentik_id="auth-ind-teacher",
    email="ind@example.com",
    display_name="Independent Teacher",
    role=IndependentUserRole.INDEPENDENT_TEACHER,
    status=IndependentUserAccountStatus.ACTIVE,
)
IND_REFERENCE = IndependentPersonalContent(
    id="ind-ref-1",
    user_id="ind-teacher-1",
    content_type=PersonalContentType.REFERENCE,
    title="My Notes",
    file_key="k",
    file_sha256="c" * 64,
    status=PersonalContentStatus.AVAILABLE,
    vector_collection="independent_personal_ind-teacher-1",
)


# --- in-memory fake repositories ---------------------------------------------


class _Store:
    users: dict[str, User] = {}
    offerings: dict[str, GradeSubjectOffering] = {}
    grades: dict[str, Grade] = {}
    subjects: dict[str, Subject] = {}
    library: dict[str, SchoolLibraryItem] = {}
    drafts: dict[str, SchoolLectureDraft] = {}
    lectures: dict[str, SchoolLecture] = {}
    profiles: dict[str, TeacherProfile] = {}
    links: list[SchoolLectureLink] = []
    assignments: list[SchoolLectureAssignment] = []
    enrollments: list[StudentEnrollment] = []
    sections: dict[str, Section] = {}
    ind_users: dict[str, IndependentUser] = {}
    ind_drafts: dict[str, IndependentLectureDraft] = {}
    ind_lectures: dict[str, IndependentLecture] = {}
    ind_personal_content: dict[str, IndependentPersonalContent] = {}


class _FakeUserRepo:
    def __init__(self, session: Any) -> None:
        pass

    async def get_by_authentik_id(self, authentik_id: str) -> User | None:
        return next((u for u in _Store.users.values() if u.authentik_id == authentik_id), None)

    async def get_by_id(self, user_id: str) -> User | None:
        return _Store.users.get(user_id)


class _FakeOfferingRepo:
    def __init__(self, session: Any) -> None:
        pass

    async def list_by_teacher(self, teacher_id: str) -> list[GradeSubjectOffering]:
        return [o for o in _Store.offerings.values() if o.assigned_teacher_id == teacher_id]

    async def get_by_id(self, id: str) -> GradeSubjectOffering | None:
        return _Store.offerings.get(id)


class _FakeGradeRepo:
    def __init__(self, session: Any) -> None:
        pass

    async def get_by_id(self, id: str) -> Grade | None:
        return _Store.grades.get(id)


class _FakeSubjectRepo:
    def __init__(self, session: Any) -> None:
        pass

    async def get_by_id(self, id: str) -> Subject | None:
        return _Store.subjects.get(id)


class _FakeLibraryRepo:
    def __init__(self, session: Any) -> None:
        pass

    async def list_for_user(self, **kwargs: Any) -> tuple[list[SchoolLibraryItem], int]:
        content_type = kwargs.get("content_type")
        rows = [
            i
            for i in _Store.library.values()
            if content_type is None or i.content_type.value == content_type
        ]
        return rows, len(rows)

    async def get_by_id(self, item_id: str) -> SchoolLibraryItem | None:
        return _Store.library.get(item_id)

    async def get_selection(self, library_item_id: str, user_id: str) -> None:
        return None


class _FakeDraftRepo:
    def __init__(self, session: Any) -> None:
        pass

    async def get_active_for_teacher(self, teacher_user_id: str) -> SchoolLectureDraft | None:
        for d in _Store.drafts.values():
            if d.teacher_user_id == teacher_user_id and d.deleted_at is None:
                return d
        return None

    async def create(self, draft: SchoolLectureDraft) -> SchoolLectureDraft:
        draft.created_at = datetime.now(timezone.utc)
        draft.updated_at = draft.created_at
        _Store.drafts[draft.id] = draft
        return draft

    async def update(self, draft: SchoolLectureDraft) -> SchoolLectureDraft:
        draft.updated_at = datetime.now(timezone.utc)
        _Store.drafts[draft.id] = draft
        return draft

    async def soft_delete(self, draft: SchoolLectureDraft) -> None:
        draft.deleted_at = datetime.now(timezone.utc)
        _Store.drafts[draft.id] = draft


class _FakeLectureRepo:
    def __init__(self, session: Any) -> None:
        pass

    async def create(self, lecture: SchoolLecture) -> SchoolLecture:
        lecture.created_at = datetime.now(timezone.utc)
        lecture.updated_at = lecture.created_at
        _Store.lectures[lecture.id] = lecture
        return lecture

    async def get_by_id(self, lecture_id: str) -> SchoolLecture | None:
        return _Store.lectures.get(lecture_id)


class _FakeProfileRepo:
    def __init__(self, session: Any) -> None:
        pass

    async def get_by_user_id(self, user_id: str) -> TeacherProfile | None:
        return _Store.profiles.get(user_id)


class _FakeLectureLinkRepo:
    def __init__(self, session: Any) -> None:
        pass

    async def list_by_lecture(self, lecture_id: str) -> list[SchoolLectureLink]:
        return [link for link in _Store.links if link.lecture_id == lecture_id]

    async def get_existing(
        self, lecture_id: str, target_grade_subject_offering_id: str
    ) -> SchoolLectureLink | None:
        return next(
            (
                link
                for link in _Store.links
                if link.lecture_id == lecture_id
                and link.target_grade_subject_offering_id == target_grade_subject_offering_id
            ),
            None,
        )

    async def create(self, link: SchoolLectureLink) -> SchoolLectureLink:
        link.created_at = datetime.now(timezone.utc)
        _Store.links.append(link)
        return link


class _FakeAssignmentRepo:
    def __init__(self, session: Any) -> None:
        pass

    async def list_by_lecture(self, lecture_id: str) -> list[SchoolLectureAssignment]:
        return [r for r in _Store.assignments if r.lecture_id == lecture_id]

    async def replace_for_lecture(
        self, lecture_id: str, assignments: list[SchoolLectureAssignment]
    ) -> list[SchoolLectureAssignment]:
        _Store.assignments[:] = [r for r in _Store.assignments if r.lecture_id != lecture_id]
        for row in assignments:
            row.created_at = datetime.now(timezone.utc)
        _Store.assignments.extend(assignments)
        return assignments


class _FakeEnrollmentRepo:
    def __init__(self, session: Any) -> None:
        pass

    async def get_active_by_student_session(
        self, student_user_id: str, academic_session: str
    ) -> StudentEnrollment | None:
        return next(
            (
                e
                for e in _Store.enrollments
                if e.student_user_id == student_user_id
                and e.academic_session == academic_session
                and e.status == StudentEnrollmentStatus.ACTIVE
            ),
            None,
        )

    async def list_active_for_grade(
        self, grade_id: str, academic_session: str
    ) -> list[StudentEnrollment]:
        return [
            e
            for e in _Store.enrollments
            if e.grade_id == grade_id
            and e.academic_session == academic_session
            and e.status == StudentEnrollmentStatus.ACTIVE
        ]


class _FakeSectionRepo:
    def __init__(self, session: Any) -> None:
        pass

    async def get_by_id(self, id: str) -> Section | None:
        return _Store.sections.get(id)

    async def list_visible_by_grade(self, grade_id: str) -> list[Section]:
        return [s for s in _Store.sections.values() if s.grade_id == grade_id]


class _FakeIndUserRepo:
    def __init__(self, session: Any) -> None:
        pass

    async def get_by_authentik_id(self, authentik_id: str) -> IndependentUser | None:
        return next((u for u in _Store.ind_users.values() if u.authentik_id == authentik_id), None)

    async def get_by_id(self, user_id: str) -> IndependentUser | None:
        return _Store.ind_users.get(user_id)


class _FakeIndLectureRepo:
    def __init__(self, session: Any) -> None:
        pass

    async def create(self, lecture: IndependentLecture) -> IndependentLecture:
        _Store.ind_lectures[lecture.id] = lecture
        return lecture

    async def get_by_id(self, lecture_id: str) -> IndependentLecture | None:
        return _Store.ind_lectures.get(lecture_id)


class _FakeIndDraftRepo:
    def __init__(self, session: Any) -> None:
        pass

    async def get_active_for_teacher(self, teacher_user_id: str) -> IndependentLectureDraft | None:
        return next(
            (d for d in _Store.ind_drafts.values() if d.teacher_user_id == teacher_user_id), None
        )

    async def create(self, draft: IndependentLectureDraft) -> IndependentLectureDraft:
        _Store.ind_drafts[draft.id] = draft
        return draft

    async def update(self, draft: IndependentLectureDraft) -> IndependentLectureDraft:
        return draft

    async def soft_delete(self, draft: IndependentLectureDraft) -> None:
        _Store.ind_drafts.pop(draft.id, None)


class _FakeIndParagraphRepo:
    def __init__(self, session: Any) -> None:
        pass

    async def list_by_version(self, lecture_version_id: str) -> list[IndependentLectureParagraph]:
        return []  # generation writes via a mocked session; not exercised in this E2E


class _FakeIndPersonalContentRepo:
    def __init__(self, session: Any) -> None:
        pass

    async def list_for_user(
        self, user_id: str, *, limit: int = 50, offset: int = 0, content_type: str | None = None
    ) -> list[IndependentPersonalContent]:
        items = [item for item in _Store.ind_personal_content.values() if item.user_id == user_id]
        if content_type is not None:
            items = [item for item in items if item.content_type.value == content_type]
        return items

    async def get_by_id(self, content_id: str) -> IndependentPersonalContent | None:
        return _Store.ind_personal_content.get(content_id)


@pytest.fixture(autouse=True)
def _patch(monkeypatch: pytest.MonkeyPatch) -> None:
    _Store.users = {TEACHER.id: TEACHER, STUDENT_1.id: STUDENT_1, STUDENT_2.id: STUDENT_2}
    _Store.offerings = {OFFERING_G9.id: OFFERING_G9, OFFERING_G10.id: OFFERING_G10}
    _Store.grades = {GRADE_9.id: GRADE_9, GRADE_10.id: GRADE_10}
    _Store.subjects = {SUBJECT.id: SUBJECT}
    _Store.library = {CURRICULUM.id: CURRICULUM, REFERENCE.id: REFERENCE}
    _Store.drafts = {}
    _Store.lectures = {}
    _Store.profiles = {PROFILE.user_id: PROFILE}
    _Store.links = []
    _Store.assignments = []
    _Store.enrollments = [ENROLLMENT_1, ENROLLMENT_2]
    _Store.sections = {SECTION_A.id: SECTION_A, SECTION_B.id: SECTION_B}
    _Store.ind_users = {IND_TEACHER.id: IND_TEACHER}
    _Store.ind_drafts = {}
    _Store.ind_lectures = {}
    _Store.ind_personal_content = {IND_REFERENCE.id: IND_REFERENCE}

    monkeypatch.setattr(service_mod, "UserRepository", _FakeUserRepo)
    monkeypatch.setattr(service_mod, "OfferingRepository", _FakeOfferingRepo)
    monkeypatch.setattr(service_mod, "GradeRepository", _FakeGradeRepo)
    monkeypatch.setattr(service_mod, "SubjectRepository", _FakeSubjectRepo)
    monkeypatch.setattr(service_mod, "SchoolLibraryRepository", _FakeLibraryRepo)
    monkeypatch.setattr(service_mod, "LectureDraftRepository", _FakeDraftRepo)
    monkeypatch.setattr(service_mod, "LectureRepository", _FakeLectureRepo)
    monkeypatch.setattr(service_mod, "TeacherProfileRepository", _FakeProfileRepo)
    monkeypatch.setattr(service_mod, "LectureLinkRepository", _FakeLectureLinkRepo)
    monkeypatch.setattr(service_mod, "LectureAssignmentRepository", _FakeAssignmentRepo)
    monkeypatch.setattr(service_mod, "StudentEnrollmentRepository", _FakeEnrollmentRepo)
    monkeypatch.setattr(service_mod, "SectionRepository", _FakeSectionRepo)

    monkeypatch.setattr(independent_service_mod, "IndependentUserRepository", _FakeIndUserRepo)
    monkeypatch.setattr(
        independent_service_mod, "IndependentLectureRepository", _FakeIndLectureRepo
    )
    monkeypatch.setattr(
        independent_service_mod, "IndependentLectureParagraphRepository", _FakeIndParagraphRepo
    )
    monkeypatch.setattr(
        independent_service_mod, "IndependentLectureDraftRepository", _FakeIndDraftRepo
    )
    monkeypatch.setattr(
        independent_service_mod,
        "IndependentPersonalContentRepository",
        _FakeIndPersonalContentRepo,
    )

    async def _noop(*args: Any, **kwargs: Any) -> None:
        return None

    monkeypatch.setattr(service_mod, "audit", _noop)
    monkeypatch.setattr(independent_service_mod, "audit", _noop)
    monkeypatch.setattr(generation_mod, "audit", _noop)
    monkeypatch.setattr(generation_mod, "notify_generation_complete", _noop)
    monkeypatch.setattr(independent_generation_mod, "audit", _noop)
    monkeypatch.setattr(independent_generation_mod, "notify_generation_complete", _noop)

    async def _fake_publish(*, event_type: str, payload: dict[str, Any]) -> None:
        return None

    monkeypatch.setattr(generation_mod, "publish_lecture_event", _fake_publish)
    monkeypatch.setattr(independent_generation_mod, "publish_lecture_event", _fake_publish)

    import app.features.lectures.independent_tasks as independent_tasks_mod
    import app.features.lectures.tasks as tasks_mod

    monkeypatch.setattr(tasks_mod.generate_lecture, "apply_async", lambda **_kwargs: None)
    monkeypatch.setattr(
        tasks_mod.generate_lecture_teacher_tips, "apply_async", lambda **_kwargs: None
    )
    monkeypatch.setattr(
        independent_tasks_mod.generate_independent_lecture, "apply_async", lambda **_kwargs: None
    )


def _claims(sub: str) -> dict[str, object]:
    return {"sub": sub, "role": "teacher"}


def _gen_session(lectures: dict[str, Any]) -> tuple[AsyncMock, list[Any]]:
    """AsyncMock session for the direct pipeline call — mirrors test_lecture_generation.py."""
    added: list[Any] = []
    session = AsyncMock()

    async def _get(model: type[Any], pk: str) -> Any:
        if model in (SchoolLecture, IndependentLecture):
            return lectures.get(pk)
        if pk == CURRICULUM.id:
            return CURRICULUM
        if pk == REFERENCE.id:
            return REFERENCE
        if pk == IND_REFERENCE.id:
            return IND_REFERENCE
        return None  # GradeSubjectOffering/Subject lookups -> no exam overlay

    session.get = AsyncMock(side_effect=_get)
    session.add = MagicMock(side_effect=lambda obj: added.append(obj))
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    return session, added


@pytest.mark.asyncio
async def test_m09_lecture_wizard_full_flow_e2e(monkeypatch: pytest.MonkeyPatch) -> None:
    claims = _claims("auth-teacher")
    svc = LectureWizardService(cast("AsyncSession", object()))  # unused except by the repos above

    # --- Steps 1-2: offerings, curricula, topics ----------------------------
    offerings = await svc.list_my_offerings(claims)
    assert {o.id for o in offerings} == {"off-g9", "off-g10"}

    curricula = await svc.list_curricula_for_offering(claims, OFFERING_G9.id)
    assert curricula[0].id == CURRICULUM.id
    assert curricula[0].is_primary is True

    topics = await svc.list_topics_for_curriculum(claims, CURRICULUM.id, OFFERING_G9.id)
    assert topics.parse_degraded is False

    # --- Step 3: references + draft auto-save/resume (Acceptance #2) -------
    refs = await svc.list_references_for_offering(claims, OFFERING_G9.id)
    assert refs[0].id == REFERENCE.id

    await svc.upsert_draft(
        claims,
        LectureDraftUpsert(
            step=3,
            data={
                "grade_subject_offering_id": OFFERING_G9.id,
                "topic": "Newton's Laws",
                "curriculum_id": CURRICULUM.id,
            },
        ),
    )
    resumed = await svc.get_draft(claims)
    assert resumed.step == 3
    assert resumed.data["topic"] == "Newton's Laws"  # draft survives a reopen

    # --- Steps 4-5: commit -> GENERATING ------------------------------------
    result = await svc.generate_from_wizard(
        claims,
        LectureGenerateRequest(
            grade_subject_offering_id=OFFERING_G9.id,
            topic="Newton's Laws",
            curriculum_id=CURRICULUM.id,
            reference_book_ids=[REFERENCE.id],
            teaching_mode=TeachingMode.AUTO,
            include_cross_grade=False,
        ),
    )
    assert result.status == LectureStatus.GENERATING.value
    lecture_id = result.lecture_id
    assert _Store.lectures[lecture_id].grade_subject_offering_id == OFFERING_G9.id

    # --- Generation: real dual-RAG pipeline, LLM mocked (Acceptance #3) ----
    async def _fake_retrieve(query: str, collection: str, **kwargs: Any) -> list[dict[str, Any]]:
        if "curriculum" in collection:
            return [
                {
                    "id": "chunk-c",
                    "score": 1.0,
                    "payload": {
                        "library_item_id": CURRICULUM.id,
                        "text": "Newton's first law: an object at rest stays at rest.",
                        "title": CURRICULUM.title,
                    },
                }
            ]
        return [
            {
                "id": "chunk-r",
                "score": 1.0,
                "payload": {
                    "library_item_id": REFERENCE.id,
                    "text": "Worked example: F = ma for a 2kg block.",
                    "title": REFERENCE.title,
                },
            }
        ]

    async def _fake_stream_chat(*_a: Any, **_k: Any) -> Any:
        raw = (
            '{"title": "Newton\'s Laws", "paragraphs": ['
            '{"text": "From curriculum: an object at rest stays at rest.", '
            '"tier": "curriculum", "book_name": "Punjab Physics 9-10", "chunk_id": "chunk-c"},'
            '{"text": "From reference: F = ma worked example.", "tier": "reference", '
            '"book_name": "Grade 9 Physics Reference", "chunk_id": "chunk-r"}'
            "]}"
        )
        for piece in [raw[i : i + 12] for i in range(0, len(raw), 12)]:
            yield piece

    monkeypatch.setattr(generation_mod, "retrieve", _fake_retrieve)
    monkeypatch.setattr(generation_mod, "stream_chat", _fake_stream_chat)
    monkeypatch.setattr(generation_mod, "append_token", AsyncMock(return_value=1))
    monkeypatch.setattr(generation_mod, "mark_complete", AsyncMock())

    gen_session, added = _gen_session(_Store.lectures)
    version_id = await run_lecture_generation(
        gen_session,
        lecture_id=lecture_id,
        school_id="school-1",
        topic="Newton's Laws",
        curriculum_id=CURRICULUM.id,
        reference_book_ids=[REFERENCE.id],
        teaching_mode="auto",
        teacher_user_id=TEACHER.id,
    )

    versions = [o for o in added if isinstance(o, SchoolLectureVersion)]
    paragraphs = [o for o in added if isinstance(o, SchoolLectureParagraph)]
    assert len(versions) == 1
    assert versions[0].version == 1
    tiers = {p.source_metadata_jsonb["tier"] for p in paragraphs}
    assert tiers == {"curriculum", "reference"}  # source badges (Acceptance #3)
    assert _Store.lectures[lecture_id].status == LectureStatus.READY_FOR_EDIT
    assert _Store.lectures[lecture_id].current_version_id == version_id

    # --- Out-of-curriculum fallback: no coverage -> web tier (Acceptance #4) -
    fallback_lecture = SchoolLecture(
        id="lec-fallback",
        school_id="school-1",
        grade_subject_offering_id=OFFERING_G9.id,
        teacher_user_id=TEACHER.id,
        title="Quantum Entanglement",
        topic="Quantum Entanglement",
        lecture_type=LectureType.MAIN,
        status=LectureStatus.GENERATING,
    )
    _Store.lectures[fallback_lecture.id] = fallback_lecture

    async def _empty_retrieve(*_a: Any, **_k: Any) -> list[dict[str, Any]]:
        return []

    async def _empty_db_chunks(_session: Any, _item_ids: list[str]) -> list[Any]:
        return []

    async def _fake_web_search(*_a: Any, **_k: Any) -> list[SearchResult]:
        return [
            SearchResult(
                url="https://example.edu/qe",
                title="Quantum Entanglement 101",
                snippet="An introduction to quantum entanglement.",
            )
        ]

    async def _fake_web_fetch(_url: str) -> str:
        return "Quantum entanglement links particle states across distance."

    async def _fake_stream_chat_web(*_a: Any, **_k: Any) -> Any:
        raw = (
            '{"title": "Quantum Entanglement", "paragraphs": ['
            '{"text": "From the web: entangled particles share state.", "tier": "web"}]}'
        )
        yield raw

    monkeypatch.setattr(generation_mod, "retrieve", _empty_retrieve)
    monkeypatch.setattr(generation_mod, "_load_db_chunks", _empty_db_chunks)
    monkeypatch.setattr(generation_mod, "web_search", _fake_web_search)
    monkeypatch.setattr(generation_mod, "web_fetch", _fake_web_fetch)
    monkeypatch.setattr(generation_mod, "stream_chat", _fake_stream_chat_web)

    fb_session, fb_added = _gen_session(_Store.lectures)
    await run_lecture_generation(
        fb_session,
        lecture_id=fallback_lecture.id,
        school_id="school-1",
        topic="Quantum Entanglement",
        curriculum_id=CURRICULUM.id,
        reference_book_ids=[],
        teaching_mode="auto",
        teacher_user_id=TEACHER.id,
    )
    fb_paragraphs = [o for o in fb_added if isinstance(o, SchoolLectureParagraph)]
    assert {p.source_metadata_jsonb["tier"] for p in fb_paragraphs} == {"web"}

    # --- Cross-grade linking: down allowed, up blocked (Acceptance #4) -----
    up_lecture = SchoolLecture(
        id="lec-g10-source",
        school_id="school-1",
        grade_subject_offering_id=OFFERING_G10.id,
        teacher_user_id=TEACHER.id,
        title="Advanced Mechanics",
        topic="Advanced Mechanics",
        lecture_type=LectureType.MAIN,
        status=LectureStatus.READY_FOR_EDIT,
        current_version_id="ver-g10",
    )
    _Store.lectures[up_lecture.id] = up_lecture

    allowed = await svc.link_lecture(
        claims, up_lecture.id, LectureLinkCreate(target_grade_subject_offering_id=OFFERING_G9.id)
    )
    assert allowed.target_grade_subject_offering_id == OFFERING_G9.id  # G10 -> G9 allowed

    with pytest.raises(PermissionDeniedError):
        await svc.link_lecture(
            claims, lecture_id, LectureLinkCreate(target_grade_subject_offering_id=OFFERING_G10.id)
        )  # G9 -> G10 blocked

    # --- Per-lecture access restriction (flow-5 §3.14) ----------------------
    restricted = await svc.set_lecture_access_settings(
        claims,
        lecture_id,
        LectureAccessSettingsUpdate(
            assignments=[
                LectureAssignmentInput(
                    scope=LectureAssignmentScope.STUDENT, student_user_id=STUDENT_1.id
                )
            ]
        ),
    )
    assert restricted.is_restricted is True

    lecture_row = _Store.lectures[lecture_id]
    assert await svc.student_can_access_lecture(STUDENT_1, lecture_row) is True
    assert await svc.student_can_access_lecture(STUDENT_2, lecture_row) is False


@pytest.mark.asyncio
async def test_m09_independent_teacher_variant_e2e(monkeypatch: pytest.MonkeyPatch) -> None:
    """Acceptance #5: independent stripped variant (own refs only, no auto-quiz)."""
    ind_svc = IndependentLectureWizardService(cast("AsyncSession", object()))
    claims: dict[str, object] = {"sub": "auth-ind-teacher", "role": "independent_teacher"}

    refs = await ind_svc.list_my_references(claims)
    assert [r.id for r in refs] == [
        IND_REFERENCE.id
    ]  # only the teacher's own pool — no school library

    await ind_svc.upsert_draft(claims, LectureDraftUpsert(step=1, data={"topic": "Photosynthesis"}))
    resumed = await ind_svc.get_draft(claims)
    assert resumed.data["topic"] == "Photosynthesis"

    result = await ind_svc.generate_from_wizard(
        claims,
        IndependentLectureGenerateRequest(
            topic="Photosynthesis",
            reference_content_ids=[IND_REFERENCE.id],
            teaching_mode=TeachingMode.AUTO,
        ),
    )
    assert result.status == LectureStatus.GENERATING.value
    lecture_id = result.lecture_id
    assert lecture_id in _Store.ind_lectures  # written to the independent schema's own table

    async def _fake_retrieve(*_a: Any, **_k: Any) -> list[dict[str, Any]]:
        return [
            {
                "id": "chunk-1",
                "score": 1.0,
                "payload": {
                    "library_item_id": IND_REFERENCE.id,
                    "text": "Photosynthesis converts light energy into chemical energy.",
                },
            }
        ]

    async def _fake_chat(*_a: Any, **_k: Any) -> str:
        return (
            '{"title": "Photosynthesis", "paragraphs": ['
            '{"text": "From my notes: light -> chemical energy.", "tier": "reference", '
            '"book_name": "My Notes"}]}'
        )

    monkeypatch.setattr(independent_generation_mod, "retrieve", _fake_retrieve)
    monkeypatch.setattr(independent_generation_mod, "chat", _fake_chat)

    gen_session, added = _gen_session(_Store.ind_lectures)
    await run_independent_lecture_generation(
        gen_session,
        lecture_id=lecture_id,
        user_id=IND_TEACHER.id,
        topic="Photosynthesis",
        reference_content_ids=[IND_REFERENCE.id],
        teaching_mode="auto",
    )

    paragraphs = [o for o in added if isinstance(o, IndependentLectureParagraph)]
    assert paragraphs and paragraphs[0].source_metadata_jsonb["tier"] == "reference"
    assert _Store.ind_lectures[lecture_id].status == LectureStatus.READY_FOR_EDIT
    # No auto-quiz artifact of any kind is produced — M-09 doesn't build quiz
    # generation at all (school or independent); nothing to assert away here
    # beyond the lecture reaching READY_FOR_EDIT without any quiz-related call.
