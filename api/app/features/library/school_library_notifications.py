"""School library notification helpers — T-065."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.grades.models import Grade, GradeStatus
from app.features.library.school_models import SchoolLibraryItem
from app.features.offerings.models import GradeSubjectOffering, OfferingStatus
from app.features.teacher_onboarding.repository import TeacherProfileRepository
from app.features.users.models import User, UserAccountStatus, UserRole
from app.features.users.repository import UserRepository
from app.infrastructure.events.content_library import publish_content_library_mutation
from app.infrastructure.notifications.content_library import notify_content_library_event


async def list_teacher_ids_for_library_tags(
    session: AsyncSession,
    *,
    school_id: str,
    subject_id: str | None,
    grade_level_ordinal: int | None,
    language: str,
    exclude_user_id: str,
) -> list[str]:
    """Teachers whose assignments/profile match library item tags (flow-3 §5.3)."""
    teachers = await UserRepository(session).list_by_school_and_role(school_id, UserRole.TEACHER)
    profile_repo = TeacherProfileRepository(session)
    matched: list[str] = []

    for teacher in teachers:
        if teacher.id == exclude_user_id or teacher.status != UserAccountStatus.ACTIVE:
            continue
        profile = await profile_repo.get_by_user_id(teacher.id)
        if profile is not None and profile.language_preference != language:
            continue
        if subject_id is None:
            matched.append(teacher.id)
            continue
        if profile is not None and subject_id in profile.subject_ids:
            if grade_level_ordinal is None or await _teacher_grade_access(
                session, teacher.id, subject_id, grade_level_ordinal
            ):
                matched.append(teacher.id)
                continue
        if await _teacher_grade_access(session, teacher.id, subject_id, grade_level_ordinal):
            matched.append(teacher.id)

    return matched


async def _teacher_grade_access(
    session: AsyncSession,
    teacher_id: str,
    subject_id: str,
    item_grade_ordinal: int | None,
) -> bool:
    stmt = (
        select(GradeSubjectOffering.id)
        .join(Grade, Grade.id == GradeSubjectOffering.grade_id)
        .where(
            GradeSubjectOffering.assigned_teacher_id == teacher_id,
            GradeSubjectOffering.subject_id == subject_id,
            GradeSubjectOffering.status == OfferingStatus.ACTIVE,
            Grade.status == GradeStatus.ACTIVE,
        )
    )
    if item_grade_ordinal is not None:
        stmt = stmt.where(Grade.level_ordinal >= item_grade_ordinal)
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None


async def notify_library_item_available(
    session: AsyncSession,
    item: SchoolLibraryItem,
) -> None:
    params = {
        "title": item.title,
        "content_type": item.content_type.value,
    }
    await notify_content_library_event(
        session=session,
        template_key="content_library.item_available",
        recipient_user_id=item.created_by,
        school_id=item.school_id,
        params=params,
        metadata={"library_item_id": item.id},
    )
    await publish_content_library_mutation(
        "item_available",
        {
            "library_item_id": item.id,
            "title": item.title,
            "content_type": item.content_type.value,
        },
        school_id=item.school_id,
        user_id=item.created_by,
    )


async def notify_library_item_failed(
    session: AsyncSession,
    item: SchoolLibraryItem,
    *,
    error: str,
) -> None:
    await notify_content_library_event(
        session=session,
        template_key="content_library.item_failed",
        recipient_user_id=item.created_by,
        school_id=item.school_id,
        params={"title": item.title, "error": error[:200]},
        metadata={"library_item_id": item.id},
    )
    await publish_content_library_mutation(
        "item_failed",
        {
            "library_item_id": item.id,
            "title": item.title,
            "error": error[:500],
        },
        school_id=item.school_id,
        user_id=item.created_by,
    )


async def notify_library_item_published(
    session: AsyncSession,
    item: SchoolLibraryItem,
    *,
    actor: User,
) -> None:
    await notify_content_library_event(
        session=session,
        template_key="content_library.item_published",
        recipient_user_id=actor.id,
        school_id=item.school_id,
        variant="publisher",
        params={"title": item.title, "actor_name": actor.display_name},
        metadata={"library_item_id": item.id},
    )

    audience_ids = await list_teacher_ids_for_library_tags(
        session,
        school_id=item.school_id,
        subject_id=item.subject_id,
        grade_level_ordinal=item.grade_level_ordinal,
        language=item.language,
        exclude_user_id=actor.id,
    )
    for teacher_id in audience_ids:
        await notify_content_library_event(
            session=session,
            template_key="content_library.item_published",
            recipient_user_id=teacher_id,
            school_id=item.school_id,
            params={"title": item.title, "actor_name": actor.display_name},
            metadata={"library_item_id": item.id},
        )

    await publish_content_library_mutation(
        "item_published",
        {
            "library_item_id": item.id,
            "title": item.title,
            "subject_id": item.subject_id,
            "grade_level_ordinal": item.grade_level_ordinal,
            "language": item.language,
        },
        school_id=item.school_id,
        user_id=actor.id,
    )


async def publish_library_item_uploaded(
    session: AsyncSession,
    item: SchoolLibraryItem,
    *,
    actor_id: str,
) -> None:
    await publish_content_library_mutation(
        "item_uploaded",
        {
            "library_item_id": item.id,
            "title": item.title,
            "content_type": item.content_type.value,
        },
        school_id=item.school_id,
        user_id=actor_id,
    )


async def publish_library_item_deleted(
    session: AsyncSession,
    item: SchoolLibraryItem,
    *,
    actor_id: str,
) -> None:
    await publish_content_library_mutation(
        "item_deleted",
        {
            "library_item_id": item.id,
            "title": item.title,
            "content_type": item.content_type.value,
        },
        school_id=item.school_id,
        user_id=actor_id,
    )
