/**
 * T-210 / T-211 — Self-study session + due flashcards + daily goal smoke (@smoke @mock).
 */
import { test, expect, type Page, type Route } from "@playwright/test";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

function envelope<T>(data: T) {
  return JSON.stringify({ data, message: "ok" });
}

async function installMocks(page: Page) {
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

    if (path.includes("/independent/students/me/onboarding")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: envelope({
          profile_complete: true,
          ready_to_study: true,
          exam_date_passed: false,
          profile: null,
        }),
      });
      return;
    }

    if (path === "/self-study/me/goal" && method === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: envelope({
          goal: {
            id: "goal-1",
            tenant_type: "independent",
            goal_date: "2026-10-15",
            goal_text: "Understand Newton's Laws",
            achieved: null,
            achievement_check_pending: true,
          },
        }),
      });
      return;
    }

    if (path === "/self-study/me/goal" && method === "PUT") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: envelope({
          id: "goal-1",
          tenant_type: "independent",
          goal_date: "2026-10-15",
          goal_text: "Understand Newton's Laws",
          achieved: null,
          achievement_check_pending: true,
        }),
      });
      return;
    }

    if (path === "/self-study/me/materials" && method === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: envelope({ items: [] }),
      });
      return;
    }

    if (path === "/self-study/me/due-flashcards" && method === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: envelope({
          items: [],
          schedule_computed: false,
          schedule_owner: "flow_9",
        }),
      });
      return;
    }

    if (path === "/self-study/me/sessions" && method === "POST") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: envelope({
          id: "sess-1",
          tenant_type: "independent",
          mode: "self_study",
          status: "active",
          material_id: null,
          study_plan_id: null,
          retrieval_primary: "student_upload_chunks",
          retrieval_overlays: ["ai_knowledge"],
          reaches_flow7: false,
        }),
      });
      return;
    }

    if (path === "/self-study/me/plans/gate") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: envelope({
          has_prep_book: false,
          allowed: false,
          error_message: "Please upload a prep question book to generate a study plan.",
        }),
      });
      return;
    }

    if (path === "/self-study/me/plans/active") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: envelope({ plan: null }),
      });
      return;
    }

    if (path === "/self-study/me/calendar/google-config") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: envelope({ enabled: false }),
      });
      return;
    }

    if (path === "/self-study/me/reminder-preferences") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: envelope({
          push_enabled: true,
          email_enabled: true,
          sms_enabled: true,
          timezone: "Asia/Karachi",
        }),
      });
      return;
    }

    if (path === "/self-study/me/entry") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: envelope({
          tenant_type: "independent",
          locked_to_self_study: true,
          active_mode: "self_study",
          state: {},
          subscription_gate: {
            enforced: false,
            allowed: true,
            max_active_plans: null,
            max_monthly_uploads: null,
          },
          lecture_mode_redirect_to: null,
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

test.describe("Self-study session @smoke @mock", () => {
  test("independent student opens session UI with goal + due flashcards", async ({ page }) => {
    await installMocks(page);
    await page.goto("/independent/student/self-study");
    await expect(page.getByTestId("self-study-session")).toBeVisible();
    await expect(page.getByTestId("self-study-goal-section")).toBeVisible();
    await expect(page.getByTestId("self-study-goal-text")).toContainText("Newton");
    await expect(page.getByTestId("due-flashcards-section")).toBeVisible();
    await expect(page.getByTestId("self-study-materials")).toBeVisible();
    await expect(page.getByTestId("material-tab-pdf")).toBeVisible();
    await page.getByTestId("self-study-start-session").click();
    await expect(page.getByTestId("self-study-hybrid-widget")).toBeVisible();
    await expect(page.getByTestId("live-feedback-daily-goal")).toContainText("Newton");
  });
});
