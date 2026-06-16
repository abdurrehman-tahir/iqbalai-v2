/**
 * T-053 — Teacher onboarding smoke test (@smoke).
 */

import { test, expect, type Page, type Route } from "@playwright/test";

const BASE_URL = process.env.E2E_BASE_URL ?? "http://localhost:3000";

function envelope<T>(data: T) {
  return JSON.stringify({ data, message: "ok" });
}

async function installTeacherMocks(page: Page) {
  let profileComplete = false;
  let assignmentCount = 0;

  await page.route(
    (url) => url.pathname.includes("/api/v1/"),
    async (route: Route) => {
      const request = route.request();
      const url = new URL(request.url());
      let path = url.pathname.replace("/api/v1", "");
      if (path.length > 1 && path.endsWith("/")) path = path.slice(0, -1);
      const method = request.method();

      if (method === "GET" && path === "/teachers/me/onboarding") {
        const ready = profileComplete && assignmentCount >= 1;
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: envelope({
            state: !profileComplete
              ? "profile_incomplete"
              : ready
                ? "ready_to_teach"
                : "profile_complete",
            profile_complete: profileComplete,
            ready_to_teach: ready,
            assignment_count: assignmentCount,
            can_create_content: ready,
            profile: profileComplete
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
        profileComplete = true;
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: envelope({
            state: "profile_complete",
            profile_complete: true,
            ready_to_teach: false,
            assignment_count: 0,
            can_create_content: false,
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

      await route.fulfill({ status: 404, body: "not mocked" });
    },
  );

  await page.addInitScript(() => {
    sessionStorage.setItem(
      "iqbalai_user",
      JSON.stringify({
        user_id: "teacher-1",
        email: "teacher@iqbalai.test",
        role: "teacher",
        tos_acceptance_required: false,
        current_tos_version_id: null,
      }),
    );
    sessionStorage.setItem("iqbalai_token", "e2e-teacher-token");
  });
}

test.describe("Teacher onboarding @smoke", () => {
  test("forces profile completion then shows awaiting-assignment banner", async ({ page }) => {
    await installTeacherMocks(page);
    await page.goto(`${BASE_URL}/teacher`);
    await expect(page).toHaveURL(/\/teacher\/onboarding/);
    await expect(page.getByText(/complete your teacher profile/i)).toBeVisible();

    await page.getByLabel(/Full name/i).fill("Ali Khan");
    await page.getByRole("checkbox").check();
    await page.getByRole("button", { name: /Save profile and continue/i }).click();

    await expect(page).toHaveURL(`${BASE_URL}/teacher`);
    await expect(page.getByText(/waiting for your Coordinator/i)).toBeVisible();
  });
});
