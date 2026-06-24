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

export function auditActionLabelKey(action: string): string | null {
  return M04_ACTION_KEYS[action] ?? null;
}

export function isFlaggedAuditEntry(entry: AuditEntry & { metadata_json?: string | null }): boolean {
  if (entry.action === "capacity.override") {
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
