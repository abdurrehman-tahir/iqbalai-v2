"""API v1 router — mounts all feature routers."""

from __future__ import annotations

from fastapi import APIRouter

from app.features.academic_sessions.router import router as academic_sessions_router
from app.features.audit.router import router as audit_router
from app.features.audit.school_admin_router import router as school_audit_router
from app.features.auth.router import router as auth_router
from app.features.bulk_imports.router import router as bulk_imports_router
from app.features.data_rights.parent_router import router as parent_data_rights_router
from app.features.data_rights.student_router import router as student_data_rights_router
from app.features.exam_frameworks.router import router as exam_frameworks_router
from app.features.exam_syllabi.router import router as syllabi_router
from app.features.files.router import router as uploads_router
from app.features.grades.router import router as grades_router
from app.features.graduation.coordinator_router import router as graduation_coordinator_router
from app.features.graduation.school_admin_router import router as graduation_school_admin_router
from app.features.graduation.student_router import router as graduation_student_router
from app.features.health.router import router as health_router
from app.features.independent_signup.router import router as independent_signup_router
from app.features.independent_student_onboarding.router import (
    router as independent_student_onboarding_router,
)
from app.features.independent_teacher_onboarding.router import (
    router as independent_teacher_onboarding_router,
)
from app.features.invites.router import router as invites_router
from app.features.library.independent_personal_router import (
    router as independent_personal_router,
)
from app.features.library.platform_library_router import router as platform_library_router
from app.features.library.router import router as library_router
from app.features.library.school_library_router import router as school_library_router
from app.features.notifications.router import router as notifications_router
from app.features.offerings.router import router as offerings_router
from app.features.parent_child_links.parent_router import router as parent_links_router
from app.features.parent_child_links.student_connections_router import (
    router as student_connections_router,
)
from app.features.parent_child_links.student_router import router as student_parent_links_router
from app.features.parent_signup.router import router as parent_signup_router
from app.features.personas.router import router as personas_router
from app.features.schools.router import router as districts_router
from app.features.schools.school_admin_router import router as school_admin_router
from app.features.schools.school_router import router as schools_router
from app.features.sections.router import router as sections_router
from app.features.smoketest.router import router as smoketest_router
from app.features.student_enrollments.router import router as student_enrollments_router
from app.features.student_onboarding.router import router as student_onboarding_router
from app.features.subjects.router import router as subjects_router
from app.features.subscriptions.router import router as subscriptions_router
from app.features.teacher_onboarding.router import router as teacher_onboarding_router
from app.features.tos.router import router as tos_router
from app.features.users.admin_router import router as admin_users_router
from app.features.users.router import router as users_router

router = APIRouter()

router.include_router(health_router, tags=["health"])
router.include_router(smoketest_router, tags=["smoketest"])
router.include_router(uploads_router, tags=["uploads"])
router.include_router(auth_router)
router.include_router(users_router)
router.include_router(admin_users_router)
router.include_router(tos_router)
router.include_router(syllabi_router)
router.include_router(exam_frameworks_router)
router.include_router(districts_router)
router.include_router(schools_router)
router.include_router(school_admin_router)
router.include_router(invites_router)
router.include_router(independent_signup_router)
router.include_router(parent_signup_router)
router.include_router(parent_links_router)
router.include_router(student_parent_links_router)
router.include_router(student_connections_router)
router.include_router(independent_teacher_onboarding_router)
router.include_router(independent_student_onboarding_router)
router.include_router(bulk_imports_router)
router.include_router(personas_router)
router.include_router(academic_sessions_router)
router.include_router(grades_router)
router.include_router(sections_router)
router.include_router(student_enrollments_router)
router.include_router(student_onboarding_router)
router.include_router(student_data_rights_router)
router.include_router(parent_data_rights_router)
router.include_router(graduation_coordinator_router)
router.include_router(graduation_school_admin_router)
router.include_router(graduation_student_router)
router.include_router(offerings_router)
router.include_router(subjects_router)
router.include_router(teacher_onboarding_router)
router.include_router(subscriptions_router)
router.include_router(library_router)
router.include_router(platform_library_router)
router.include_router(independent_personal_router)
router.include_router(school_library_router)
router.include_router(notifications_router)
router.include_router(audit_router)
router.include_router(school_audit_router)
