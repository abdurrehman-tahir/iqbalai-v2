/**
 * T-222 — M-17 self-study journey smoke (@smoke @mock).
 * LLM/OCR/FCM/SMS/email/Google Calendar env-unset; no live network.
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
        body: envelope({ goal: null }),
      });
      return;
    }

    if (path === "/self-study/me/materials" && method === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: envelope({
          items: [
            {
              id: "mat-prep",
              tenant_type: "independent",
              title: "Prep book",
              source_type: "pdf",
              book_type: "prep_questions",
              added_to_library: true,
              storage_key: "k",
              has_ocr_text: true,
            },
          ],
        }),
      });
      return;
    }

    if (path === "/self-study/me/plans/gate" && method === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: envelope({
          has_prep_book: true,
          allowed: true,
          error_message: null,
        }),
      });
      return;
    }

    if (path === "/self-study/me/plans/conversation" && method === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: envelope({
          step: 0,
          total_steps: 5,
          question: "What exam are you preparing for?",
          answers: {},
          complete: false,
          gate_passed: true,
        }),
      });
      return;
    }

    if (path === "/self-study/me/plans/active" && method === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: envelope({
          plan: {
            id: "plan-1",
            tenant_type: "independent",
            status: "active",
            exam_date: "2026-11-01",
            daily_hours: 2,
            strong_topics: [],
            granularity_current: "day",
            items: [
              {
                id: "item-1",
                granularity: "day",
                start_date: "2026-10-16",
                end_date: "2026-10-16",
                est_minutes: 60,
                subject_color: "#2563eb",
                tasks: [{ title: "Mechanics", kind: "practice" }],
              },
            ],
          },
        }),
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

    if (path === "/self-study/me/reminder-preferences" && method === "GET") {
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

    if (path === "/self-study/me/due-flashcards") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: envelope({ items: [], schedule_computed: false, schedule_owner: "flow_9" }),
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
          subscription_gate: { enforced: false, allowed: true, max_active_plans: null, max_monthly_uploads: null },
          lecture_mode_redirect_to: "/independent/student/self-study",
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

test.describe("M-17 self-study journey @smoke @mock", () => {
  test("independent student sees plan calendar, ICS, reminders; no #72; Google hidden", async ({
    page,
  }) => {
    await installMocks(page);
    await page.goto("/independent/student/self-study");

    await expect(page.getByTestId("study-plan-panel")).toBeVisible();
    await expect(page.getByTestId("study-plan-calendar")).toBeVisible();
    await expect(page.getByTestId("study-plan-ics")).toBeVisible();
    await expect(page.getByTestId("study-plan-google")).toHaveCount(0);
    await expect(page.getByTestId("reminder-preferences")).toBeVisible();
    await expect(page.getByTestId("reminder-push")).toBeVisible();
    // #72 hidden for independent
    await expect(page.getByTestId("self-study-privacy")).toHaveCount(0);
  });
});
