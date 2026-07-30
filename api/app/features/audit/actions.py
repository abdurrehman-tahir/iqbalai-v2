"""Registered audit action identifiers — M-03/M-04/M-06/M-07."""

from __future__ import annotations

# M-04 — school content library
SCHOOL_LIBRARY_ITEM_UPLOADED = "school_library_item.uploaded"
SCHOOL_LIBRARY_ITEM_PUBLISHED = "school_library_item.published"
SCHOOL_LIBRARY_ITEM_DELETED = "school_library_item.deleted"
SCHOOL_LIBRARY_ITEM_INGESTED = "school_library_item.ingested"
SCHOOL_LIBRARY_ITEM_SELECTION_REMOVED = "school_library_item.selection_removed"

# M-04 — teacher capacity
CAPACITY_UPDATED = "capacity.updated"
CAPACITY_OVERRIDE = "capacity.override"

# M-06 — enrollment + onboarding
STUDENT_ENROLLED = "student.enrolled"
BULK_IMPORT_DRY_RUN = "bulk_import.dry_run_complete"
BULK_IMPORT_COMMITTED = "bulk_import.committed"
PARENT_SIGNUP = "user.parent_signup"
STUDENT_PROFILE_BASIC = "student.profile_basic_completed"
STUDENT_MODES_SELECTED = "student.modes_selected"
STUDENT_EXAM_DATE_SET = "student.exam_date_set"

# M-06 — parent links
PARENT_LINK_REQUESTED = "parent_link.requested"
PARENT_LINK_APPROVED = "parent_link.approved"
PARENT_LINK_REVOKED_BY_PARENT = "parent_link.revoked_by_parent"
PARENT_LINK_REVOKED_BY_STUDENT = "parent_link.revoked_by_student"
PARENT_LINK_RE_REQUESTED = "parent_link.re_requested"

# M-06 — data rights (elevated)
DATA_RIGHTS_EXPORT_REQUESTED = "data_rights.export_requested"
DATA_RIGHTS_DELETION_REQUESTED = "data_rights.deletion_requested"
DATA_RIGHTS_DELETION_CANCELLED = "data_rights.deletion_cancelled"

# M-06 — graduation (elevated)
GRADUATION_REQUESTED = "graduation.requested"
GRADUATION_APPROVED = "graduation.approved"
GRADUATION_MIGRATED = "graduation.migrated"
GRADUATION_MIGRATION_FAILED = "graduation.migration_failed"

# M-07 — exam frameworks (platform-tier lifecycle). Strings match what the
# exam_frameworks service emits (note: refresh uses ``refresh_triggered``).
FRAMEWORK_CREATED = "framework.created"
FRAMEWORK_UPDATED = "framework.updated"
FRAMEWORK_DELETED = "framework.deleted"
FRAMEWORK_RESEARCH_TRIGGERED = "framework.research_triggered"
FRAMEWORK_APPROVED = "framework.approved"
FRAMEWORK_REJECTED = "framework.rejected"
FRAMEWORK_PUBLISHED = "framework.published"
FRAMEWORK_REFRESH_TRIGGERED = "framework.refresh_triggered"
FRAMEWORK_DEPRECATED = "framework.deprecated"
FRAMEWORK_APPROVAL_REMINDER = "framework.approval_reminder"
FRAMEWORK_APPROVAL_ESCALATED = "framework.approval_escalated"

# M-08 — mode / diagnostic / Cognitive DNA (T-110)
STUDENT_MODE_CHANGED = "student.mode_changed"  # low-noise free toggle
DIAGNOSTIC_STARTED = "diagnostic.started"
DIAGNOSTIC_COMPLETED = "diagnostic.completed"
DIAGNOSTIC_RETAKEN = "diagnostic.retaken"
COGNITIVE_DNA_SEEDED = "cognitive_dna.seeded"

ELEVATED_AUDIT_ACTIONS = frozenset(
    {
        CAPACITY_OVERRIDE,
        DATA_RIGHTS_EXPORT_REQUESTED,
        DATA_RIGHTS_DELETION_REQUESTED,
        DATA_RIGHTS_DELETION_CANCELLED,
        GRADUATION_MIGRATED,
        GRADUATION_MIGRATION_FAILED,
        # Approval + publish expose AI content to students; deprecation + escalation
        # change what students may select / need urgent attention (T-098 Acceptance #2).
        FRAMEWORK_APPROVED,
        FRAMEWORK_PUBLISHED,
        FRAMEWORK_DEPRECATED,
        FRAMEWORK_APPROVAL_ESCALATED,
    }
)

M04_AUDIT_ACTIONS = frozenset(
    {
        SCHOOL_LIBRARY_ITEM_UPLOADED,
        SCHOOL_LIBRARY_ITEM_PUBLISHED,
        SCHOOL_LIBRARY_ITEM_DELETED,
        SCHOOL_LIBRARY_ITEM_INGESTED,
        SCHOOL_LIBRARY_ITEM_SELECTION_REMOVED,
        CAPACITY_UPDATED,
        CAPACITY_OVERRIDE,
    }
)

M06_AUDIT_ACTIONS = frozenset(
    {
        STUDENT_ENROLLED,
        BULK_IMPORT_DRY_RUN,
        BULK_IMPORT_COMMITTED,
        PARENT_SIGNUP,
        STUDENT_PROFILE_BASIC,
        STUDENT_MODES_SELECTED,
        STUDENT_EXAM_DATE_SET,
        PARENT_LINK_REQUESTED,
        PARENT_LINK_APPROVED,
        PARENT_LINK_REVOKED_BY_PARENT,
        PARENT_LINK_REVOKED_BY_STUDENT,
        PARENT_LINK_RE_REQUESTED,
        DATA_RIGHTS_EXPORT_REQUESTED,
        DATA_RIGHTS_DELETION_REQUESTED,
        DATA_RIGHTS_DELETION_CANCELLED,
        GRADUATION_REQUESTED,
        GRADUATION_APPROVED,
        GRADUATION_MIGRATED,
        GRADUATION_MIGRATION_FAILED,
    }
)

M07_AUDIT_ACTIONS = frozenset(
    {
        FRAMEWORK_CREATED,
        FRAMEWORK_UPDATED,
        FRAMEWORK_DELETED,
        FRAMEWORK_RESEARCH_TRIGGERED,
        FRAMEWORK_APPROVED,
        FRAMEWORK_REJECTED,
        FRAMEWORK_PUBLISHED,
        FRAMEWORK_REFRESH_TRIGGERED,
        FRAMEWORK_DEPRECATED,
        FRAMEWORK_APPROVAL_REMINDER,
        FRAMEWORK_APPROVAL_ESCALATED,
    }
)

# Mode toggle is registered but low-noise (not elevated); diagnostic/DNA are the
# meaningful M-08 security/compliance trail (T-110 Acceptance #1–#3).
M08_AUDIT_ACTIONS = frozenset(
    {
        STUDENT_MODE_CHANGED,
        DIAGNOSTIC_STARTED,
        DIAGNOSTIC_COMPLETED,
        DIAGNOSTIC_RETAKEN,
        COGNITIVE_DNA_SEEDED,
    }
)

REGISTERED_AUDIT_ACTIONS = (
    M04_AUDIT_ACTIONS | M06_AUDIT_ACTIONS | M07_AUDIT_ACTIONS | M08_AUDIT_ACTIONS
)
