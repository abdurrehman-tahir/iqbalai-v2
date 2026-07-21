/**
 * T-070 — Independent teacher onboarding smoke test (@smoke).
 */

import { test, expect, type Page, type Route } from "@playwright/test";

const BASE_URL = process.env.E2E_BASE_URL ?? "http://localhost:3000";

function envelope<T>(data: T) {
  return JSON.stringify({ data, message: "ok" });
}

async function installIndependentTeacherMocks(page: Page) {
  let profileComplete = false;

  // T-247: the shell resolves "who am I" via GET /auth/me (cookie session)
  // since T-245. The onboarding route below is scoped to /independent/teachers/me
  // and won't match /auth/me, so register a dedicated handler for it.
  await page.route(
    (url) => url.pathname.endsWith("/api/v1/auth/me"),
    async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: envelope({
          user_id: "ind-teacher-1",
          email: "teacher@example.com",
          role: "independent_teacher",
          tenant_type: "independent",
          school_id: null,
          district_id: null,
        }),
      });
    },
  );

  await page.route(
    (url) => url.pathname.includes("/api/v1/independent/teachers/me"),
    async (route: Route) => {
      const method = route.request().method();
      const path = new URL(route.request().url()).pathname.replace("/api/v1", "");

      if (method === "GET" && path === "/independent/teachers/me/onboarding") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: envelope({
            state: profileComplete ? "ready_to_use" : "profile_incomplete",
            profile_complete: profileComplete,
            ready_to_use: profileComplete,
            can_create_content: profileComplete,
            profile: profileComplete
              ? {
                  user_id: "ind-teacher-1",
                  name: "Indie Teacher",
                  language_preference: "en",
                  profile_completed_at: "2026-06-22T00:00:00Z",
                }
              : null,
          }),
        });
        return;
      }

      if (method === "PUT" && path === "/independent/teachers/me/profile") {
        profileComplete = true;
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: envelope({
            state: "ready_to_use",
            profile_complete: true,
            ready_to_use: true,
            can_create_content: true,
            profile: {
              user_id: "ind-teacher-1",
              name: "Indie Teacher",
              language_preference: "en",
              profile_completed_at: "2026-06-22T00:00:00Z",
            },
          }),
        });
        return;
      }

      await route.continue();
    },
  );
}

test.describe("@smoke independent teacher onboarding", () => {
  test.beforeEach(async ({ page }) => {
    await installIndependentTeacherMocks(page);
  });

  test("onboarding gate redirects and profile completion reaches ready", async ({ page }) => {
    await page.goto(`${BASE_URL}/independent/teacher`);
    await expect(page).toHaveURL(/\/independent\/teacher\/onboarding/);
    await page.getByLabel(/Full name/i).fill("Indie Teacher");
    await page.getByRole("button", { name: /Save profile and continue/i }).click();
    await expect(page).toHaveURL(/\/independent\/teacher$/);
    await expect(page.getByText(/ready to use IqbalAI/i)).toBeVisible();
  });
});
