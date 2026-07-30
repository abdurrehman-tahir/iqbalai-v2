/**
 * T-114 — Lecture wizard steps 1–2 smoke (@smoke).
 */

import { test, expect, type Page, type Route } from "@playwright/test";

const BASE_URL = process.env.E2E_BASE_URL ?? "http://localhost:3000";

function envelope<T>(data: T) {
  return JSON.stringify({ data, message: "ok" });
}

async function installWizardMocks(page: Page) {
  await page.route(
    (url) => url.pathname.includes("/api/v1/") || url.pathname.includes("/auth/me"),
    async (route: Route) => {
      const request = route.request();
      const url = new URL(request.url());
      let path = url.pathname.replace("/api/v1", "");
      if (path.length > 1 && path.endsWith("/")) path = path.slice(0, -1);
      const method = request.method();

      if (method === "GET" && path === "/auth/me") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: envelope({
            user_id: "teacher-1",
            email: "teacher@test.com",
            role: "teacher",
            tenant_type: "school",
            school_id: "school-1",
            district_id: null,
          }),
        });
        return;
      }

      if (method === "GET" && path === "/teachers/me/onboarding") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: envelope({
            state: "ready_to_teach",
            profile_complete: true,
            ready_to_teach: true,
            assignment_count: 1,
            can_create_content: true,
            teacher_capacity: 5,
            capacity_below_assignments: false,
            profile: null,
          }),
        });
        return;
      }

      if (method === "GET" && path === "/teachers/me/offerings") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: envelope([
            {
              id: "off-1",
              grade_id: "g-1",
              grade_name: "Grade 9",
              grade_level_ordinal: 9,
              subject_id: "s-1",
              subject_name: "Physics",
              academic_session: "2025-2026",
            },
          ]),
        });
        return;
      }

      if (method === "GET" && path === "/teachers/me/lecture-draft") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: envelope({
            id: null,
            teacher_user_id: "teacher-1",
            step: 1,
            data: {},
            updated_at: null,
          }),
        });
        return;
      }

      if (method === "PUT" && path === "/teachers/me/lecture-draft") {
        const body = request.postDataJSON() as { step: number; data: object };
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: envelope({
            id: "draft-1",
            teacher_user_id: "teacher-1",
            step: body.step,
            data: body.data,
            updated_at: "2026-07-30T00:00:00Z",
          }),
        });
        return;
      }

      if (method === "GET" && path === "/teachers/me/lecture-wizard/curricula") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: envelope([
            {
              id: "curr-1",
              title: "Punjab Physics 9",
              subject_id: "s-1",
              grade_level_ordinal: 9,
              is_primary: true,
              parse_degraded: false,
              topic_tree_jsonb: null,
            },
          ]),
        });
        return;
      }

      if (method === "GET" && path === "/teachers/me/lecture-wizard/topics") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: envelope({
            curriculum_id: "curr-1",
            parse_degraded: false,
            topics: [{ path: "Forces > Newton", label: "Newton" }],
          }),
        });
        return;
      }

      if (method === "GET" && path === "/teachers/me/lecture-wizard/references") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: envelope([
            {
              id: "ref-1",
              title: "Halliday",
              subject_id: "s-1",
              grade_level_ordinal: 9,
              language: "en",
              is_cross_grade: false,
            },
          ]),
        });
        return;
      }

      if (method === "GET" && path === "/teachers/me/lecture-wizard/estimate") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: envelope({
            estimated_seconds: 120,
            reference_count: 1,
            teaching_mode: "auto",
          }),
        });
        return;
      }

      if (method === "POST" && path === "/teachers/me/lecture-wizard/generate") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: envelope({
            lecture_id: "lec-1",
            status: "generating",
            estimated_seconds: 120,
          }),
        });
        return;
      }

      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: envelope({}),
      });
    }
  );
}

test.describe("Lecture wizard @smoke", () => {
  test("teacher can complete wizard through Generate → GENERATING", async ({ page }) => {
    await installWizardMocks(page);
    await page.goto(`${BASE_URL}/teacher/lectures/new`);

    await expect(page.getByRole("heading", { name: /Create a lecture/i })).toBeVisible();
    await page.getByLabel(/Grade-Subject offering/i).selectOption("off-1");
    await expect(page.getByText("Forces > Newton")).toBeVisible();
    await page.getByText("Forces > Newton").click();
    await page.getByRole("button", { name: /Continue/i }).click();

    await expect(page.getByText(/Step 2 — Confirm curriculum/i)).toBeVisible();
    await page.getByRole("button", { name: /Continue/i }).click();

    await expect(page.getByText(/Step 3 — Select reference/i)).toBeVisible();
    await page.getByText("Halliday").click();
    await page.getByRole("button", { name: /Continue/i }).click();

    await expect(page.getByText(/Step 4 — Teaching mode/i)).toBeVisible();
    await page.getByText(/Auto — AI writes/i).click();
    await page.getByRole("button", { name: /Continue/i }).click();

    await expect(page.getByText(/Step 5 — Confirm/i)).toBeVisible();
    await expect(page.getByText(/about 120 seconds/i)).toBeVisible();
    await page.getByRole("button", { name: /Generate lecture/i }).click();
    await expect(page.getByText(/Generation started/i)).toBeVisible();
    await expect(page.getByText(/GENERATING/i)).toBeVisible();
  });
});
