"""Next-day review card service — M-16 (Flow 7 §3.2–§3.8, §4).

Access (Flow 7 §4 / ARCH §6.19): the owning teacher sees and acts on their own
cards (with student names); Coordinator sees cards in their school read-only
and aggregate-only; School/District/Platform Admin see in scope and may
override the teacher's card actions (audit-logged as elevated). Independent
users never reach this surface — reviews live in the school schema only.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from app.features.audit.actions import (
    REVIEW_CLUSTER_SKIPPED,
    REVIEW_DISMISSED,
    REVIEW_MINI_PUBLISHED,
    REVIEW_OVERRIDE_ACTION,
)
from app.features.lectures.events import publish_lecture_event
from app.features.lectures.models import (
    LectureStatus,
    LectureType,
    SchoolLecture,
    SchoolLectureVersion,
)
from app.features.next_day_review.assembly import _offering_label
from app.features.next_day_review.distribution import (
    MINI_LECTURE_ASSIGNED_EVENT,
    assign_recipients,
    notify_recipients,
    triggering_students,
)
from app.features.next_day_review.models import (
    LectureReview,
    LectureReviewStatus,
    ReviewReply,
    SkippedCluster,
)
from app.features.next_day_review.reflection import record_reflection
from app.features.next_day_review.regeneration import pick_cluster, skipped_refs
from app.features.next_day_review.schemas import (
    ReviewClusterSnapshot,
    ReviewClusterView,
    ReviewDetailRead,
    ReviewQuestionView,
    ReviewReplyCreate,
    ReviewReplyRead,
    ReviewSummaryRead,
)
from app.features.schools.models import School
from app.features.users.models import User, UserRole
from app.features.users.repository import UserRepository
from app.infrastructure.audit.log import audit

logger = structlog.get_logger(__name__)

MINI_PREVIEW_CHARS = 200
# Action ids recorded in ``lecture_reviews.acted_actions`` (Flow 7 §3.6).
ACTION_REFLECT = "reflect"
ACTION_REPLY = "reply"
ACTION_SKIP = "skip_cluster"
ACTION_PUBLISH_MINI = "publish_mini"
ACTION_EDIT_MAIN = "edit_main"
ACTION_DISMISS = "dismiss"

_OVERRIDE_ROLES = frozenset(
    {UserRole.SCHOOL_ADMIN, UserRole.DISTRICT_ADMIN, UserRole.PLATFORM_ADMIN}
)
# A mini from T-198 lands in READY_FOR_EDIT; PUBLISHED allows a re-publish (§5.4).
_PUBLISHABLE = frozenset(
    {LectureStatus.READY_FOR_EDIT, LectureStatus.READY_FOR_PUBLISH, LectureStatus.PUBLISHED}
)
_TAG_RE = re.compile(r"<[^>]+>")
_MD_RE = re.compile(r"[#*_`>\[\]]")


def plain_preview(body: str, limit: int = MINI_PREVIEW_CHARS) -> str:
    """First ~``limit`` chars of a lecture body with HTML/markdown markers stripped."""
    text = _MD_RE.sub("", _TAG_RE.sub(" ", body))
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit].rstrip() + "…"


class ReviewAccess:
    """Resolved viewer of one review: who they are and what they may do."""

    def __init__(self, user: User, lecture: SchoolLecture, review: LectureReview) -> None:
        self.user = user
        self.lecture = lecture
        self.review = review
        self.is_owner = user.role == UserRole.TEACHER and lecture.teacher_user_id == user.id
        self.can_override = user.role in _OVERRIDE_ROLES
        # Archived / soft-deleted parent lectures keep their reviews read-only.
        self.read_only = lecture.status == LectureStatus.ARCHIVED or lecture.deleted_at is not None

    @property
    def can_act(self) -> bool:
        return not self.read_only and (self.is_owner or self.can_override)


class NextDayReviewService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._users = UserRepository(session)

    # --- access -------------------------------------------------------------------

    async def _require_user(self, claims: dict[str, object]) -> User:
        user = await self._users.get_by_authentik_id(str(claims.get("sub", "")))
        if user is None or user.deleted_at is not None:
            raise NotFoundError("User profile not found")
        if user.role in (UserRole.STUDENT, UserRole.PARENT):
            raise PermissionDeniedError("Teacher, Coordinator, or Admin role required")
        return user

    async def _in_scope(self, user: User, lecture: SchoolLecture) -> bool:
        if user.role == UserRole.TEACHER:
            return lecture.teacher_user_id == user.id and lecture.school_id == user.school_id
        if user.role in (UserRole.COORDINATOR, UserRole.SCHOOL_ADMIN):
            return lecture.school_id == user.school_id
        if user.role == UserRole.DISTRICT_ADMIN:
            school = await self._session.get(School, lecture.school_id)
            return school is not None and school.district_id == user.district_id
        return user.role == UserRole.PLATFORM_ADMIN

    async def _load(self, claims: dict[str, object], review_id: str) -> ReviewAccess:
        user = await self._require_user(claims)
        review = await self._session.get(LectureReview, review_id)
        if review is None:
            raise NotFoundError("Review not found")
        lecture = await self._session.get(SchoolLecture, review.lecture_id)
        # Out-of-scope is a 404, never a 403 (§6.19 — don't leak existence).
        if lecture is None or not await self._in_scope(user, lecture):
            raise NotFoundError("Review not found")
        if lecture.deleted_at is not None and user.role != UserRole.PLATFORM_ADMIN:
            # Soft-deleted parent: kept for audit, hidden from active surfaces (§5.5).
            raise NotFoundError("Review not found")
        return ReviewAccess(user, lecture, review)

    # --- reads (T-201 / T-206) ---------------------------------------------------------

    @staticmethod
    def _snapshots(review: LectureReview) -> list[ReviewClusterSnapshot]:
        return [ReviewClusterSnapshot.model_validate(c) for c in review.clusters_jsonb or []]

    async def _summary(self, review: LectureReview, lecture: SchoolLecture) -> ReviewSummaryRead:
        snaps = self._snapshots(review)
        return ReviewSummaryRead(
            id=review.id,
            lecture_id=lecture.id,
            lecture_title=lecture.title,
            offering_label=await _offering_label(self._session, review.gso_id),
            review_date=review.review_date,
            generated_at=review.generated_at,
            status=review.status,
            pending_action=review.pending_action,
            dismissed_at=review.dismissed_at,
            acted_actions=list(review.acted_actions or []),
            critical_count=sum(1 for s in snaps if s.column == "critical"),
            high_frequency_count=sum(1 for s in snaps if s.column == "high_frequency"),
            read_only=lecture.status == LectureStatus.ARCHIVED,
        )

    async def list_reviews(
        self, claims: dict[str, object], *, lecture_id: str | None = None
    ) -> list[ReviewSummaryRead]:
        """Newest-first reviews the caller may see; ``lecture_id`` = a lecture's Reviews tab.

        Reviews never expire (Flow 7 §3.8) — the full history is returned.
        """
        user = await self._require_user(claims)
        stmt = (
            select(LectureReview, SchoolLecture)
            .join(SchoolLecture, SchoolLecture.id == LectureReview.lecture_id)
            .where(LectureReview.generated_at.is_not(None), SchoolLecture.deleted_at.is_(None))
            .order_by(LectureReview.review_date.desc(), LectureReview.created_at.desc())
        )
        if lecture_id is not None:
            stmt = stmt.where(LectureReview.lecture_id == lecture_id)
        if user.role == UserRole.TEACHER:
            stmt = stmt.where(SchoolLecture.teacher_user_id == user.id)
        elif user.role in (UserRole.COORDINATOR, UserRole.SCHOOL_ADMIN):
            stmt = stmt.where(SchoolLecture.school_id == user.school_id)
        elif user.role == UserRole.DISTRICT_ADMIN:
            stmt = stmt.join(School, School.id == SchoolLecture.school_id).where(
                School.district_id == user.district_id
            )
        rows = (await self._session.execute(stmt)).all()
        return [await self._summary(review, lecture) for review, lecture in rows]

    async def _student_names(self, ids: set[str]) -> dict[str, str]:
        if not ids:
            return {}
        result = await self._session.execute(
            select(User.id, User.display_name).where(User.id.in_(ids))
        )
        return {str(uid): str(name) for uid, name in result.all()}

    async def _mini_state(self, review: LectureReview) -> tuple[str | None, bool]:
        if not review.mini_lecture_id:
            return None, False
        mini = await self._session.get(SchoolLecture, review.mini_lecture_id)
        if mini is None:
            return None, False
        preview: str | None = None
        if mini.current_version_id:
            version = await self._session.get(SchoolLectureVersion, mini.current_version_id)
            if version is not None:
                preview = plain_preview(version.body or "")
        return preview, mini.status == LectureStatus.PUBLISHED

    async def get_review(self, claims: dict[str, object], review_id: str) -> ReviewDetailRead:
        access = await self._load(claims, review_id)
        return await self._detail(access)

    async def _detail(self, access: ReviewAccess) -> ReviewDetailRead:
        review, lecture = access.review, access.lecture
        snaps = self._snapshots(review)
        skipped = {
            str(ref)
            for ref in (
                await self._session.execute(
                    select(SkippedCluster.cluster_ref).where(SkippedCluster.review_id == review.id)
                )
            )
            .scalars()
            .all()
        }
        names: dict[str, str] = {}
        if access.is_owner:
            names = await self._student_names(
                {q.student_user_id for s in snaps for q in s.questions if q.student_user_id}
            )

        def _view(snap: ReviewClusterSnapshot) -> ReviewClusterView:
            questions = [
                ReviewQuestionView(
                    question_id=q.question_id,
                    question_text=q.question_text,
                    # Names + ids are teacher-only; higher roles get aggregate wording.
                    student_user_id=q.student_user_id if access.is_owner else None,
                    student_name=names.get(q.student_user_id) if access.is_owner else None,
                    paragraph_id=q.paragraph_id,
                    source_chunk_id=q.source_chunk_id,
                    occurred_at=q.occurred_at,
                )
                for q in snap.questions
            ]
            return ReviewClusterView(
                cluster_ref=snap.cluster_ref,
                lecture_id=snap.lecture_id,
                column=snap.column,
                question_count=snap.question_count,
                unique_student_count=snap.unique_student_count,
                criticality=snap.criticality,
                representative_question=snap.representative_question,
                mini_lecture_id=snap.mini_lecture_id,
                skipped=snap.cluster_ref in skipped,
                questions=questions,
            )

        replies: list[ReviewReplyRead] = []
        if access.is_owner:
            reply_rows = (
                await self._session.execute(
                    select(ReviewReply)
                    .where(ReviewReply.review_id == review.id)
                    .order_by(ReviewReply.created_at.asc())
                )
            ).scalars()
            replies = [ReviewReplyRead.model_validate(r) for r in reply_rows.all()]

        preview, published = await self._mini_state(review)
        summary = await self._summary(review, lecture)
        return ReviewDetailRead(
            **summary.model_dump(exclude={"read_only"}),
            read_only=access.read_only,
            ai_summary=review.ai_summary,
            reflective_prompt=review.reflective_prompt,
            reflected=ACTION_REFLECT in (review.acted_actions or []),
            mini_lecture_id=review.mini_lecture_id,
            mini_preview=preview,
            mini_published=published,
            critical=[_view(s) for s in snaps if s.column == "critical"],
            high_frequency=[_view(s) for s in snaps if s.column == "high_frequency"],
            replies=replies,
            is_owner=access.is_owner,
            can_act=access.can_act,
        )

    # --- reflective prompt (T-202) ------------------------------------------------------

    async def reflect(
        self, claims: dict[str, object], review_id: str, response: str
    ) -> ReviewDetailRead:
        """Store the owning teacher's reflection; nobody else may answer (Flow 7 §4)."""
        access = await self._load(claims, review_id)
        self._require_owner(access)
        if not access.review.reflective_prompt:
            raise ValidationError("This review has no reflective question")
        await record_reflection(
            self._session,
            teacher_user_id=access.user.id,
            prompt=access.review.reflective_prompt,
            response=response.strip(),
        )
        self._record_action(access.review, ACTION_REFLECT)
        await self._session.commit()
        return await self._detail(access)

    # --- drill-down: reply / skip / regenerate (T-203) ----------------------------------

    def _cluster(self, review: LectureReview, cluster_ref: str) -> ReviewClusterSnapshot:
        for snap in self._snapshots(review):
            if snap.cluster_ref == cluster_ref:
                return snap
        raise NotFoundError("Cluster not found on this review")

    async def reply(
        self, claims: dict[str, object], review_id: str, payload: ReviewReplyCreate
    ) -> ReviewDetailRead:
        """Teacher replies to one student whose question is in the cluster."""
        access = await self._load(claims, review_id)
        self._require_owner(access)
        snap = self._cluster(access.review, payload.cluster_ref)
        if payload.student_user_id not in {q.student_user_id for q in snap.questions}:
            raise ValidationError("That student did not ask a question in this cluster")
        self._session.add(
            ReviewReply(
                review_id=access.review.id,
                cluster_id=payload.cluster_ref,
                student_user_id=payload.student_user_id,
                body=payload.body.strip(),
            )
        )
        self._record_action(access.review, ACTION_REPLY)
        await self._session.commit()
        return await self._detail(access)

    async def skip(
        self, claims: dict[str, object], review_id: str, cluster_ref: str
    ) -> ReviewDetailRead:
        """Exclude a cluster from mini-lecture regeneration (idempotent)."""
        access = await self._load(claims, review_id)
        self._require_owner(access)
        self._cluster(access.review, cluster_ref)
        if cluster_ref not in await skipped_refs(self._session, access.review.id):
            self._session.add(
                SkippedCluster(
                    review_id=access.review.id, cluster_ref=cluster_ref, skipped_at=self._now()
                )
            )
            self._record_action(access.review, ACTION_SKIP)
            await audit(
                session=self._session,
                action=REVIEW_CLUSTER_SKIPPED,
                actor_id=access.user.id,
                actor_role=access.user.role.value,
                target_type="lecture_review",
                target_id=access.review.id,
                school_id=access.lecture.school_id,
                metadata={"cluster_ref": cluster_ref},
            )
            await self._session.commit()
        return await self._detail(access)

    async def regenerate_mini(self, claims: dict[str, object], review_id: str) -> ReviewDetailRead:
        """Queue a fresh mini-lecture for the top non-skipped cluster."""
        access = await self._require_actor(claims, review_id, action="regenerate_mini")
        skipped = await skipped_refs(self._session, access.review.id)
        if pick_cluster(self._snapshots(access.review), skipped) is None:
            raise ValidationError("Every cluster on this review is skipped")
        from app.features.next_day_review.tasks import regenerate_mini

        regenerate_mini.apply_async(
            kwargs={"school_id": access.lecture.school_id, "review_id": access.review.id}
        )
        await self._session.commit()
        return await self._detail(access)

    # --- targeted distribution (T-204) --------------------------------------------------

    async def publish_mini(self, claims: dict[str, object], review_id: str) -> ReviewDetailRead:
        """Publish the card's mini-lecture to the students who triggered it."""
        access = await self._require_actor(claims, review_id, action=ACTION_PUBLISH_MINI)
        review = access.review
        if not review.mini_lecture_id:
            raise ValidationError("This review has no mini-lecture to publish")
        mini = await self._session.get(SchoolLecture, review.mini_lecture_id)
        if mini is None or mini.lecture_type != LectureType.MINI:
            raise NotFoundError("Mini-lecture not found")
        if mini.status not in _PUBLISHABLE or mini.current_version_id is None:
            raise ValidationError("The mini-lecture is not ready to publish yet")

        candidates = triggering_students(
            self._snapshots(review),
            mini_lecture_id=mini.id,
            skipped=await skipped_refs(self._session, review.id),
        )
        recipients = await assign_recipients(
            self._session,
            mini=mini,
            gso_id=review.gso_id,
            candidates=candidates,
            actor_user_id=access.user.id,
        )
        was_published = mini.status == LectureStatus.PUBLISHED
        mini.status = LectureStatus.PUBLISHED
        self._record_action(review, ACTION_PUBLISH_MINI)
        review.status = LectureReviewStatus.COMPLETED
        await audit(
            session=self._session,
            action=REVIEW_MINI_PUBLISHED,
            actor_id=access.user.id,
            actor_role=access.user.role.value,
            target_type="lecture",
            target_id=mini.id,
            school_id=access.lecture.school_id,
            metadata={
                "review_id": review.id,
                "recipient_count": len(recipients),
                "republish": was_published,
                "override": not access.is_owner,
            },
        )
        await self._session.commit()

        await publish_lecture_event(
            event_type=MINI_LECTURE_ASSIGNED_EVENT,
            payload={
                "lecture_id": mini.id,
                "parent_lecture_id": mini.parent_lecture_id,
                "review_id": review.id,
                "school_id": mini.school_id,
                "teacher_user_id": mini.teacher_user_id,
                "tenant_type": "school",
                "lecture_type": LectureType.MINI.value,
                "recipient_user_ids": recipients,
            },
        )
        await notify_recipients(self._session, mini=mini, recipients=recipients)
        return await self._detail(access)

    # --- card actions (T-205) -----------------------------------------------------------

    async def edit_main(self, claims: dict[str, object], review_id: str) -> ReviewDetailRead:
        """Record "Edit Main Lecture"; the client then opens Flow 5 edit mode."""
        access = await self._require_actor(claims, review_id, action=ACTION_EDIT_MAIN)
        self._record_action(access.review, ACTION_EDIT_MAIN)
        access.review.status = LectureReviewStatus.COMPLETED
        await self._session.commit()
        return await self._detail(access)

    async def dismiss(self, claims: dict[str, object], review_id: str) -> ReviewDetailRead:
        """Dismiss without action — recoverable via ``reopen`` (Flow 7 §3.6)."""
        access = await self._require_actor(claims, review_id, action=ACTION_DISMISS)
        review = access.review
        review.dismissed_at = self._now()
        review.status = LectureReviewStatus.DISMISSED
        self._record_action(review, ACTION_DISMISS)
        await audit(
            session=self._session,
            action=REVIEW_DISMISSED,
            actor_id=access.user.id,
            actor_role=access.user.role.value,
            target_type="lecture_review",
            target_id=review.id,
            school_id=access.lecture.school_id,
            metadata={"override": not access.is_owner},
        )
        await self._session.commit()
        return await self._detail(access)

    async def reopen(self, claims: dict[str, object], review_id: str) -> ReviewDetailRead:
        """Undo a dismissal; the card is pending again (earlier actions are kept)."""
        access = await self._require_actor(claims, review_id, action="reopen")
        review = access.review
        if review.status != LectureReviewStatus.DISMISSED:
            raise ValidationError("Only a dismissed review can be reopened")
        review.dismissed_at = None
        review.status = LectureReviewStatus.PENDING
        review.pending_action = True
        await self._session.commit()
        return await self._detail(access)

    # --- shared mutation helpers ---------------------------------------------------------

    async def _require_actor(
        self, claims: dict[str, object], review_id: str, *, action: str
    ) -> ReviewAccess:
        """Owner, or an admin override (School/District/Platform) — audited as elevated."""
        access = await self._load(claims, review_id)
        if access.read_only:
            raise ValidationError("This review is read-only")
        if not access.can_act:
            raise PermissionDeniedError("Only the lecture's teacher or an admin can do this")
        if not access.is_owner:
            await audit(
                session=self._session,
                action=REVIEW_OVERRIDE_ACTION,
                actor_id=access.user.id,
                actor_role=access.user.role.value,
                target_type="lecture_review",
                target_id=access.review.id,
                school_id=access.lecture.school_id,
                metadata={"action": action},
            )
        return access

    @staticmethod
    def _require_owner(access: ReviewAccess) -> None:
        """Teacher-only actions (reflect, reply, skip) — no admin override (Flow 7 §4)."""
        if not access.is_owner:
            raise PermissionDeniedError("Only the lecture's teacher can do this")
        if access.read_only:
            raise ValidationError("This review is read-only")

    @staticmethod
    def _record_action(review: LectureReview, action: str) -> None:
        """Append an action (multiple allowed, Flow 7 §3.6) and clear pending."""
        actions = list(review.acted_actions or [])
        if action not in actions:
            actions.append(action)
        # Reassign so SQLAlchemy sees the JSONB change.
        review.acted_actions = actions
        review.pending_action = False
        if review.acted_at is None:
            review.acted_at = datetime.now(timezone.utc)

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)
