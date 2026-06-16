import { describe, expect, it } from "vitest";
import { auditActionLabelKey, isFlaggedAuditEntry } from "@/lib/audit/actionLabels";

describe("audit action labels (T-066)", () => {
  it("maps M-04 library actions to label keys", () => {
    expect(auditActionLabelKey("school_library_item.published")).toBe(
      "school_library_item_published",
    );
  });

  it("detects flagged capacity override entries", () => {
    expect(
      isFlaggedAuditEntry({
        id: "1",
        action: "capacity.override",
        actor_id: "admin",
        target_type: "user",
        target_id: "t1",
        created_at: "2026-01-01T00:00:00Z",
      }),
    ).toBe(true);
  });
});
