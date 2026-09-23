/**
 * T-150 — Auto-quiz + publish smoke (@smoke @mock).
 * Mirrors M-11 acceptance: dashboard quizzes → attempt → supportive results.
 */
import { test, expect, type Page, type Route } from "@playwright/test";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

function envelope<T>(data: T) {
  return JSON.stringify({ data, message: "ok" });
}

async function installMocks(page: Page) {
  let submitted = false;

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

    if (path === "/students/me/mode") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: envelope({
          active_mode: "lecture",
          mode_state: { lecture: {}, self_study: {} },
          lecture_mode_enabled: true,
          self_study_mode_enabled: true,
        }),
      });
      return;
    }

    if (path.startsWith("/students/me/link-requests") || path.startsWith("/students/me/connections")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: envelope({ pending: [], access_state: "UNLINKED", linked_parents: [], link_history: [] }),
      });
      return;
    }

    if (method === "GET" && path === "/students/me/quizzes") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: envelope([
          {
            assignment_id: "asg-1",
            quiz_id: "quiz-1",
            lecture_id: "lec-1",
            lecture_topic: "Forces",
            lecture_title: "Newton",
            question_count: 1,
            status: submitted ? "completed" : "published",
            assigned_at: "2026-09-01T00:00:00Z",
          },
        ]),
      });
      return;
    }

    if (method === "GET" && path === "/students/me/quizzes/asg-1") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: envelope({
          assignment_id: "asg-1",
          quiz_id: "quiz-1",
          lecture_id: "lec-1",
          lecture_topic: "Forces",
          status: "published",
          questions: [
            {
              id: "q1",
              ordinal: 1,
              stem: "What is force?",
              options: [
                { key: "A", text: "A push or pull" },
                { key: "B", text: "A color" },
              ],
            },
          ],
        }),
      });
      return;
    }

    if (method === "POST" && path === "/students/me/quizzes/asg-1/submit") {
      submitted = true;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: envelope({
          assignment_id: "asg-1",
          attempt_id: "att-1",
          score: 1,
          max_score: 1,
          status: "completed",
          questions: [
            {
              question_id: "q1",
              ordinal: 1,
              stem: "What is force?",
              selected: "A",
              correct_answer: "A",
              is_correct: true,
              source_excerpt: "Force causes acceleration.",
            },
          ],
        }),
      });
      return;
    }

    await route.fulfill({
      status: 404,
      contentType: "application/json",
      body: JSON.stringify({ detail: `unmocked ${method} ${path}` }),
    });
  });
}

test.describe("M-11 auto-quiz smoke @smoke @mock", () => {
  test("dashboard quiz → attempt → results", async ({ page }) => {
    await installMocks(page);
    await page.addInitScript(() => {
      window.localStorage.setItem("iqbalai_access_token", "mock-token");
    });

    await page.goto("/student");
    await expect(page.getByTestId("student-quizzes")).toBeVisible();
    await expect(page.getByText("Forces")).toBeVisible();

    await page.getByRole("link", { name: /Take quiz/i }).click();
    await expect(page.getByTestId("quiz-attempt")).toBeVisible();
    await page.getByLabel(/A push or pull/i).check();
    await page.getByRole("button", { name: /Submit answers/i }).click();
    await expect(page.getByTestId("quiz-results")).toBeVisible();
    await expect(page.getByText(/Score: 1 \/ 1/i)).toBeVisible();
  });
});
