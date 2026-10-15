/**
 * T-210 — Self-study session + due flashcards smoke (@smoke @mock).
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
        body: envelope({ ready_to_study: true, exam_date_passed: false, profile: null }),
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

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: envelope({}),
    });
  });
}

test.describe("Self-study session @smoke @mock", () => {
  test("independent student opens session UI with due flashcards surface", async ({ page }) => {
    await installMocks(page);
    await page.goto("/independent/student/self-study");
    await expect(page.getByTestId("self-study-session")).toBeVisible();
    await expect(page.getByTestId("due-flashcards-section")).toBeVisible();
    await page.getByTestId("self-study-start-session").click();
    await expect(page.getByTestId("self-study-hybrid-widget")).toBeVisible();
  });
});
