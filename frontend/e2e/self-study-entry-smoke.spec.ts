/**
 * T-209 — Self-study entering-mode smoke (@smoke @mock).
 *
 * Independent student lands on self-study home (no mode switcher) and
 * subscription gate is present but no-op.
 */
import { test, expect, type Page, type Route } from "@playwright/test";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

function envelope<T>(data: T) {
  return JSON.stringify({ data, message: "ok" });
}

async function installIndependentMocks(page: Page) {
  await page.route(`${API_BASE}/**`, async (route: Route) => {
    const url = new URL(route.request().url());
    let path = url.pathname.replace("/api/v1", "");
    if (path.length > 1 && path.endsWith("/")) path = path.slice(0, -1);
    const method = route.request().method();

    if (method === "GET" && path === "/auth/me") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: envelope({
          user_id: "ind-1",
          email: "indie@example.com",
          role: "independent_student",
          tenant_type: "independent",
          school_id: null,
          district_id: null,
        }),
      });
      return;
    }

    if (path.includes("/independent/students/me/onboarding") && method === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: envelope({
          profile_complete: true,
          ready_to_study: true,
          exam_date_passed: false,
          show_complete_profile_banner: false,
          profile: null,
        }),
      });
      return;
    }

    if (path === "/self-study/me/entry" && method === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: envelope({
          tenant_type: "independent",
          locked_to_self_study: true,
          active_mode: "self_study",
          state: {
            last_goal_id: null,
            last_material_id: null,
            last_plan_view: null,
          },
          subscription_gate: {
            enforced: false,
            allowed: true,
            max_active_plans: null,
            max_monthly_uploads: null,
          },
          lecture_mode_redirect_to: "/independent/student",
        }),
      });
      return;
    }

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: envelope({}),
    });
  });
}

test.describe("Self-study entry @smoke @mock", () => {
  test("independent student opens self-study home with no-op subscription gate", async ({
    page,
  }) => {
    await installIndependentMocks(page);
    await page.goto("/independent/student");
    await expect(page.getByTestId("independent-self-study-dashboard")).toBeVisible();
    await expect(page.getByTestId("self-study-section")).toBeVisible();
    await expect(page.getByTestId("self-study-subscription-gate")).toBeVisible();
    await expect(page.getByTestId("lecture-section")).toHaveCount(0);
  });
});
