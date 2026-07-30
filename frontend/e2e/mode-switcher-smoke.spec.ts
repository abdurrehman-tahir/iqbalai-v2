/**
 * T-101 — Mode Switcher smoke (@smoke @mock).
 *
 * School student sees Lecture ⇄ Self-Study radiogroup; independent student does not.
 */
import { test, expect, type Page, type Route } from "@playwright/test";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

function envelope<T>(data: T) {
  return JSON.stringify({ data, message: "ok" });
}

async function installStudentMocks(page: Page, role: "student" | "independent_student") {
  let activeMode: "lecture" | "self_study" = "lecture";

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
          user_id: "u-1",
          email: role === "student" ? "student@example.com" : "indie@example.com",
          role,
          tenant_type: role === "student" ? "school" : "independent",
          school_id: role === "student" ? "school-1" : null,
          district_id: null,
        }),
      });
      return;
    }

    if (role === "student" && path === "/students/me/mode") {
      if (method === "GET") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: envelope({
            active_mode: activeMode,
            mode_state: { lecture: {}, self_study: {} },
            lecture_mode_enabled: true,
            self_study_mode_enabled: true,
          }),
        });
        return;
      }
      if (method === "PUT") {
        const body = route.request().postDataJSON() as { active_mode: "lecture" | "self_study" };
        activeMode = body.active_mode;
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: envelope({
            active_mode: activeMode,
            mode_state: { lecture: {}, self_study: {} },
            lecture_mode_enabled: true,
            self_study_mode_enabled: true,
          }),
        });
        return;
      }
    }

    if (path === "/students/me/onboarding" || path.includes("/independent/students/me/onboarding")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: envelope({
          ready_to_study: true,
          show_complete_profile_banner: false,
          exam_date_set: false,
          profile: null,
        }),
      });
      return;
    }

    if (path.includes("link") || path.includes("connections") || path.includes("parent")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: envelope({ pending: [], linked_parents: [], access_state: "UNLINKED", link_history: [] }),
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

test.describe("Mode Switcher (T-101) @smoke @mock", () => {
  test("school student sees switcher and can toggle to Self-Study @smoke", async ({ page }) => {
    await installStudentMocks(page, "student");
    await page.goto("/student");
    const group = page.getByRole("radiogroup", { name: /Study mode/i });
    await expect(group).toBeVisible();
    await expect(page.getByTestId("lecture-section")).toBeVisible();
    await page.getByRole("radio", { name: /Self-Study/i }).click();
    await expect(page.getByTestId("self-study-section")).toBeVisible();
    await expect(page.getByTestId("lecture-section")).toHaveCount(0);
  });

  test("independent student has no mode switcher @smoke", async ({ page }) => {
    await installStudentMocks(page, "independent_student");
    await page.goto("/independent/student");
    await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
    await expect(page.getByRole("radiogroup", { name: /Study mode/i })).toHaveCount(0);
  });
});
