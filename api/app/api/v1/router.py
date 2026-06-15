"""API v1 router — mounts all feature routers."""

from __future__ import annotations

from fastapi import APIRouter

from app.features.audit.router import router as audit_router
from app.features.audit.school_admin_router import router as school_audit_router
from app.features.auth.router import router as auth_router
from app.features.bulk_imports.router import router as bulk_imports_router
from app.features.exam_syllabi.router import router as syllabi_router
from app.features.files.router import router as uploads_router
from app.features.health.router import router as health_router
from app.features.invites.router import router as invites_router
from app.features.library.router import router as library_router
from app.features.notifications.router import router as notifications_router
from app.features.personas.router import router as personas_router
from app.features.schools.router import router as districts_router
from app.features.schools.school_admin_router import router as school_admin_router
from app.features.schools.school_router import router as schools_router
from app.features.smoketest.router import router as smoketest_router
from app.features.academic_sessions.router import router as academic_sessions_router
from app.features.grades.router import router as grades_router
from app.features.sections.router import router as sections_router
from app.features.subjects.router import router as subjects_router
from app.features.subscriptions.router import router as subscriptions_router
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
router.include_router(districts_router)
router.include_router(schools_router)
router.include_router(school_admin_router)
router.include_router(invites_router)
router.include_router(bulk_imports_router)
router.include_router(personas_router)
router.include_router(academic_sessions_router)
router.include_router(grades_router)
router.include_router(sections_router)
router.include_router(subjects_router)
router.include_router(subscriptions_router)
router.include_router(library_router)
router.include_router(notifications_router)
router.include_router(audit_router)
router.include_router(school_audit_router)
