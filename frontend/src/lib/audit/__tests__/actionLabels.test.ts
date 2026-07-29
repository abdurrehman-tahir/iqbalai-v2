import { describe, expect, it } from "vitest";
import { auditActionLabelKey, isFlaggedAuditEntry } from "@/lib/audit/actionLabels";

describe("audit action labels (T-066)", () => {
  it("maps M-04 library actions to label keys", () => {
    expect(auditActionLabelKey("school_library_item.published")).toBe(
      "school_library_item_published",
    );
  });

  it("maps M-08 diagnostic actions to label keys", () => {
    expect(auditActionLabelKey("diagnostic.completed")).toBe("diagnostic_completed");
    expect(auditActionLabelKey("cognitive_dna.seeded")).toBe("cognitive_dna_seeded");
    expect(auditActionLabelKey("student.mode_changed")).toBe("student_mode_changed");
  });
});
