/**
 * T-105 — Diagnostic taking UI smoke (@smoke @mock).
 */
import { test, expect, type Page, type Route } from "@playwright/test";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

function envelope<T>(data: T) {
  return JSON.stringify({ data, message: "ok" });
}

async function installMocks(page: Page) {
  let answers: Record<string, string> = {};
  const questions = [
    {
      id: "q1",
      prompt: "Which is a force unit?",
      choices: ["Newton", "Kilogram"],
      topic: "Newton's Laws",
    },
  ];

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
          email: "student@example.com",
          role: "student",
          tenant_type: "school",
          school_id: "school-1",
          district_id: null,
        }),
      });
      return;
    }

    if (path === "/students/me/onboarding") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: envelope({ ready_to_study: true, show_complete_profile_banner: false }),
      });
      return;
    }

    if (method === "POST" && path === "/students/me/diagnostics/start") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: envelope({
          id: "d1",
          tenant_type: "school",
          student_user_id: "u-1",
          subject_id: "demo-subject",
          status: "in_progress",
          questions,
          answers,
          expires_at: new Date(Date.now() + 86_400_000).toISOString(),
        }),
      });
      return;
    }

    if (method === "PUT" && path === "/students/me/diagnostics/d1/answers") {
      const body = route.request().postDataJSON() as { answers: Record<string, string> };
      answers = { ...answers, ...body.answers };
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: envelope({
          id: "d1",
          tenant_type: "school",
          student_user_id: "u-1",
          subject_id: "demo-subject",
          status: "in_progress",
          questions,
          answers,
          expires_at: new Date(Date.now() + 86_400_000).toISOString(),
        }),
      });
      return;
    }

    if (method === "POST" && path === "/students/me/diagnostics/d1/complete") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: envelope({
          diagnostic: {
            id: "d1",
            tenant_type: "school",
            student_user_id: "u-1",
            status: "completed",
            questions,
            answers,
          },
          focus_areas: [
            { topic: "Newton's Laws", suggestion: "Spend more time on Newton's Laws." },
          ],
          timed_out: false,
          coaching_summary: "Nice work. Coaching guidance only.",
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

test.describe("Diagnostic taking (T-105) @smoke @mock", () => {
  test("student completes diagnostic and sees focus areas not grades @smoke", async ({
    page,
  }) => {
    await installMocks(page);
    await page.goto("/student/diagnostics");
    await expect(page.getByTestId("diagnostic-taking")).toBeVisible();
    await page.getByRole("radio", { name: /Newton/i }).click();
    await page.getByRole("button", { name: /Finish/i }).click();
    await expect(page.getByTestId("diagnostic-results")).toBeVisible();
    await expect(page.getByText(/Areas to focus on/i)).toBeVisible();
    await expect(page.getByText(/never shows marks/i)).toBeVisible();
  });
});
