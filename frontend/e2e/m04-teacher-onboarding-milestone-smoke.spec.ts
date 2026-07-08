/**
 * T-067 — M-04 milestone demo flow smoke (@smoke).
 *
 * Covers: teacher onboarding → ready to teach → library cross-grade filter →
 * reference privacy toggle + publish → capacity self-edit.
 * Uses committed fixture PDF (no network fetch).
 */

import fs from "fs";
import path from "path";
import { test, expect, type Page, type Route } from "@playwright/test";

const BASE_URL = process.env.E2E_BASE_URL ?? "http://localhost:3000";
const FIXTURE_PDF = path.join(__dirname, "fixtures", "sample.pdf");

function envelope<T>(data: T) {
  return JSON.stringify({ data, message: "ok" });
}

type MilestoneState = {
  profileComplete: boolean;
  assignmentCount: number;
  teacherCapacity: number;
  referenceVisibility: "private" | "school_public";
  referenceStatus: "pending" | "ingesting" | "available";
};

const LIBRARY_ITEMS = [
  {
    id: "curriculum-g8",
    title: "Punjab Physics Grade 8",
    content_type: "curriculum",
    grade_level_ordinal: 8,
    ingestion_status: "available",
    visibility: "school_public",
    created_by: "coord-1",
  },
  {
    id: "curriculum-g9",
    title: "Punjab Physics Grade 9",
    content_type: "curriculum",
    grade_level_ordinal: 9,
    ingestion_status: "available",
    visibility: "school_public",
    created_by: "coord-1",
  },
  {
    id: "curriculum-g10",
    title: "Punjab Physics Grade 10",
    content_type: "curriculum",
    grade_level_ordinal: 10,
    ingestion_status: "available",
    visibility: "school_public",
    created_by: "coord-1",
  },
  {
    id: "reference-item-1",
    title: "Physics Notes",
    content_type: "reference",
    grade_level_ordinal: null,
    ingestion_status: "available",
    visibility: "private",
    created_by: "teacher-1",
  },
] as const;

function itemPayload(
  item: (typeof LIBRARY_ITEMS)[number],
  overrides: Record<string, unknown> = {},
) {
  return {
    id: item.id,
    school_id: "school-1",
    title: item.title,
    content_type: item.content_type,
    language: "en",
    subject_id: item.content_type === "curriculum" ? "subj-1" : null,
    grade_level_ordinal: item.grade_level_ordinal,
    storage_key: `school-library/school-1/${item.id}.pdf`,
    sha256: "a".repeat(64),
    ingestion_status: item.ingestion_status,
    topic_tree_jsonb:
      item.content_type === "curriculum"
        ? {
            chapters: [{ title: "Mechanics", sections: [{ title: "Motion", sub_topics: ["Speed"] }] }],
            parse_degraded: false,
          }
        : null,
    created_by: item.created_by,
    visibility: item.visibility,
    created_at: "2026-06-16T00:00:00Z",
    updated_at: "2026-06-16T00:00:00Z",
    ...overrides,
  };
}

function filterLibraryItems(gradeContext: string | null) {
  if (!gradeContext) {
    return LIBRARY_ITEMS;
  }
  const context = Number.parseInt(gradeContext, 10);
  return LIBRARY_ITEMS.filter(
    (item) =>
      item.grade_level_ordinal === null || item.grade_level_ordinal <= context,
  );
}

async function installM04Mocks(page: Page, state: MilestoneState) {
  await page.route(
    (url) => url.pathname.includes("/api/v1/"),
    async (route: Route) => {
      const request = route.request();
      const url = new URL(request.url());
      let path = url.pathname.replace("/api/v1", "");
      if (path.length > 1 && path.endsWith("/")) path = path.slice(0, -1);
      const method = request.method();

      if (method === "GET" && path === "/teachers/me/onboarding") {
        const ready = state.profileComplete && state.assignmentCount >= 1;
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: envelope({
            state: !state.profileComplete
              ? "profile_incomplete"
              : ready
                ? "ready_to_teach"
                : "profile_complete",
            profile_complete: state.profileComplete,
            ready_to_teach: ready,
            assignment_count: state.assignmentCount,
            can_create_content: ready,
            teacher_capacity: state.teacherCapacity,
            capacity_below_assignments: state.teacherCapacity < state.assignmentCount,
            profile: state.profileComplete
              ? {
                  user_id: "teacher-1",
                  name: "Ali Khan",
                  region_province: "Punjab",
                  region_district: null,
                  bio: null,
                  language_preference: "en",
                  subject_ids: ["subj-1"],
                  profile_completed_at: "2026-06-16T00:00:00Z",
                }
              : null,
          }),
        });
        return;
      }

      if (method === "GET" && path === "/teachers/me/subject-options") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: envelope([
            {
              id: "subj-1",
              school_id: "school-1",
              name: "Physics",
              language: "en",
              status: "active",
              created_at: "2026-06-01T00:00:00Z",
            },
          ]),
        });
        return;
      }

      if (method === "PUT" && path === "/teachers/me/profile") {
        state.profileComplete = true;
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: envelope({
            state: "profile_complete",
            profile_complete: true,
            ready_to_teach: false,
            assignment_count: 0,
            can_create_content: false,
            teacher_capacity: state.teacherCapacity,
            capacity_below_assignments: false,
            profile: {
              user_id: "teacher-1",
              name: "Ali Khan",
              region_province: "Punjab",
              region_district: null,
              bio: null,
              language_preference: "en",
              subject_ids: ["subj-1"],
              profile_completed_at: "2026-06-16T00:00:00Z",
            },
          }),
        });
        return;
      }

      if (method === "PATCH" && path === "/teachers/me/capacity") {
        const body = request.postDataJSON() as { teacher_capacity: number };
        state.teacherCapacity = body.teacher_capacity;
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: envelope({
            teacher_capacity: state.teacherCapacity,
            assignment_count: state.assignmentCount,
            capacity_below_assignments: state.teacherCapacity < state.assignmentCount,
          }),
        });
        return;
      }

      if (method === "GET" && (path === "/subjects/" || path === "/subjects")) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: envelope([{ id: "subj-1", name: "Physics", language: "en", status: "active" }]),
        });
        return;
      }

      if (method === "GET" && (path === "/grades/" || path === "/grades")) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: envelope([
            { id: "grade-8", name: "Grade 8", level_ordinal: 8, status: "active" },
            { id: "grade-9", name: "Grade 9", level_ordinal: 9, status: "active" },
            { id: "grade-10", name: "Grade 10", level_ordinal: 10, status: "active" },
          ]),
        });
        return;
      }

      if (method === "GET" && (path === "/school/library" || path === "/school/library/")) {
        const gradeContext = url.searchParams.get("grade_level_ordinal");
        const visible = filterLibraryItems(gradeContext).map((item) =>
          itemPayload(item, {
            visibility:
              item.id === "reference-item-1" ? state.referenceVisibility : item.visibility,
            ingestion_status:
              item.id === "reference-item-1" ? state.referenceStatus : item.ingestion_status,
          }),
        );
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: envelope({ items: visible, total: visible.length }),
        });
        return;
      }

      if (method === "POST" && path === "/school/library") {
        state.referenceVisibility =
          url.searchParams.get("visibility") === "school_public" ? "school_public" : "private";
        state.referenceStatus = "pending";
        await route.fulfill({
          status: 202,
          contentType: "application/json",
          body: envelope({
            item: itemPayload(LIBRARY_ITEMS[3], {
              visibility: state.referenceVisibility,
              ingestion_status: "pending",
            }),
            storage_deduplicated: false,
            selection_created: true,
            message: "ok",
          }),
        });
        return;
      }

      if (method === "POST" && path === "/school/library/reference-item-1/publish") {
        state.referenceVisibility = "school_public";
        state.referenceStatus = "available";
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: envelope(
            itemPayload(LIBRARY_ITEMS[3], {
              visibility: "school_public",
              ingestion_status: "available",
            }),
          ),
        });
        return;
      }

      if (method === "GET" && path.startsWith("/school/library/") && path !== "/school/library") {
        const itemId = path.slice("/school/library/".length).split("/")[0];
        const base =
          LIBRARY_ITEMS.find((item) => item.id === itemId) ?? LIBRARY_ITEMS[1];
        if (base.id === "reference-item-1" && state.referenceStatus === "pending") {
          state.referenceStatus = "available";
        }
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: envelope(
            itemPayload(base, {
              visibility:
                base.id === "reference-item-1" ? state.referenceVisibility : base.visibility,
              ingestion_status:
                base.id === "reference-item-1" ? state.referenceStatus : base.ingestion_status,
            }),
          ),
        });
        return;
      }

      await route.continue();
    },
  );
}

function seedTeacherSession(page: Page) {
  return page.addInitScript(() => {
    sessionStorage.setItem(
      "iqbalai_user",
      JSON.stringify({
        user_id: "teacher-1",
        email: "teacher@test.com",
        role: "teacher",
        school_id: "school-1",
        tos_acceptance_required: false,
        current_tos_version_id: null,
      }),
    );
  });
}

test.describe("M-04 teacher onboarding milestone @smoke", () => {
  test("full milestone demo flow", async ({ page }) => {
    const state: MilestoneState = {
      profileComplete: false,
      assignmentCount: 0,
      teacherCapacity: 5,
      referenceVisibility: "private",
      referenceStatus: "available",
    };

    await seedTeacherSession(page);
    await installM04Mocks(page, state);

    const pdfBuffer = fs.readFileSync(FIXTURE_PDF);
    expect(pdfBuffer.subarray(0, 5).toString()).toBe("%PDF-");

    // 1. Teacher onboarding — profile completion
    await page.goto(`${BASE_URL}/teacher/onboarding`);
    await expect(page.getByText(/complete your teacher profile/i)).toBeVisible();
    await page.getByLabel(/Full name/i).fill("Ali Khan");
    await page.getByRole("checkbox").check();
    await page.getByRole("button", { name: /Save profile and continue/i }).click();
    await expect(page).toHaveURL(`${BASE_URL}/teacher`);
    await expect(page.getByText(/waiting for your Coordinator/i)).toBeVisible();

    // 2. Assignment → ready to teach
    state.assignmentCount = 1;
    await page.goto(`${BASE_URL}/teacher`);
    await expect(page.getByText(/ready to teach/i)).toBeVisible({ timeout: 15_000 });

    // 3. Library browse — cross-grade filter (Grade 9 hides Grade 10)
    await page.goto(`${BASE_URL}/teacher/library`);
    await expect(page.getByText("Punjab Physics Grade 10")).toBeVisible();
    await page.locator("#library-grade").selectOption("9");
    await expect(page.getByText("Punjab Physics Grade 9")).toBeVisible();
    await expect(page.getByText("Punjab Physics Grade 8")).toBeVisible();
    await expect(page.getByText("Punjab Physics Grade 10")).not.toBeVisible();

    // 4. Curriculum detail shows topic tree after ingestion
    await page.goto(`${BASE_URL}/teacher/library/curriculum/curriculum-g9`);
    await expect(page.getByText("Mechanics")).toBeVisible({ timeout: 15_000 });

    // 5. Reference upload private by default → publish one-way
    await page.goto(`${BASE_URL}/teacher/library/reference/upload`);
    await expect(page.getByLabel(/Make available to the school/i)).not.toBeChecked();
    await page.getByLabel(/^Title/i).fill("Physics Notes");
    await page.getByLabel(/Reference PDF/i).setInputFiles({
      name: "sample.pdf",
      mimeType: "application/pdf",
      buffer: pdfBuffer,
    });
    const uploadButton = page.getByRole("button", { name: /Upload reference book/i });
    await expect(uploadButton).toBeEnabled({ timeout: 10_000 });
    await uploadButton.click();
    await expect(page).toHaveURL(/\/teacher\/library\/reference\/reference-item-1$/);
    await expect(page.getByText("Private — only you")).toBeVisible({ timeout: 15_000 });
    await page.getByRole("button", { name: /Make available to school/i }).click();
    await expect(page.getByText("School public")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText(/cannot be made private/i)).toBeVisible();

    // 6. Capacity self-edit on dashboard
    await page.goto(`${BASE_URL}/teacher`);
    await page.getByLabel(/^Capacity/i).fill("8");
    await page.getByRole("button", { name: /Save capacity/i }).click();
    await expect(page.getByText(/Capacity saved/i)).toBeVisible({ timeout: 10_000 });
  });
});
