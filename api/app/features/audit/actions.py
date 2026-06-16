"""Registered audit action identifiers — M-03 structure + M-04 library/capacity (T-066)."""

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
