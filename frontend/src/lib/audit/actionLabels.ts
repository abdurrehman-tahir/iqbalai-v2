import type { AuditEntry } from "@/lib/api";

const M04_ACTION_KEYS: Record<string, string> = {
  "school_library_item.uploaded": "school_library_item_uploaded",
  "school_library_item.published": "school_library_item_published",
  "school_library_item.deleted": "school_library_item_deleted",
  "school_library_item.ingested": "school_library_item_ingested",
  "school_library_item.selection_removed": "school_library_item_selection_removed",
  "capacity.updated": "capacity_updated",
  "capacity.override": "capacity_override",
};

const M06_ACTION_KEYS: Record<string, string> = {
  "student.enrolled": "student_enrolled",
  "bulk_import.dry_run_complete": "bulk_import_dry_run_complete",
  "bulk_import.committed": "bulk_import_committed",
  "user.parent_signup": "user_parent_signup",
  "student.profile_basic_completed": "student_profile_basic_completed",
  "student.modes_selected": "student_modes_selected",
  "student.exam_date_set": "student_exam_date_set",
  "parent_link.requested": "parent_link_requested",
  "parent_link.approved": "parent_link_approved",
  "parent_link.revoked_by_parent": "parent_link_revoked_by_parent",
  "parent_link.revoked_by_student": "parent_link_revoked_by_student",
  "parent_link.re_requested": "parent_link_re_requested",
  "data_rights.export_requested": "data_rights_export_requested",
  "data_rights.deletion_requested": "data_rights_deletion_requested",
  "data_rights.deletion_cancelled": "data_rights_deletion_cancelled",
  "graduation.requested": "graduation_requested",
  "graduation.approved": "graduation_approved",
  "graduation.migrated": "graduation_migrated",
  "graduation.migration_failed": "graduation_migration_failed",
};

const M08_ACTION_KEYS: Record<string, string> = {
  "student.mode_changed": "student_mode_changed",
  "diagnostic.started": "diagnostic_started",
  "diagnostic.completed": "diagnostic_completed",
  "diagnostic.retaken": "diagnostic_retaken",
  "cognitive_dna.seeded": "cognitive_dna_seeded",
};

export function auditActionLabelKey(action: string): string | null {
  return M04_ACTION_KEYS[action] ?? M06_ACTION_KEYS[action] ?? M08_ACTION_KEYS[action] ?? null;
}

const ELEVATED_ACTIONS = new Set([
  "capacity.override",
  "data_rights.export_requested",
  "data_rights.deletion_requested",
  "data_rights.deletion_cancelled",
  "graduation.migrated",
  "graduation.migration_failed",
]);

export function isFlaggedAuditEntry(entry: AuditEntry & { metadata_json?: string | null }): boolean {
  if (ELEVATED_ACTIONS.has(entry.action)) {
    return true;
  }
  if (!entry.metadata_json) {
    return false;
  }
  try {
    const metadata = JSON.parse(entry.metadata_json) as { flagged?: boolean };
    return metadata.flagged === true;
  } catch {
    return false;
  }
}
