/**
 * T-184 — M-14 live feedback + stuck nudge + adaptation smoke (@smoke @mock).
 * LLM / NATS / WebSocket use test doubles — no live external network.
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

    if (
      path.startsWith("/students/me/link-requests") ||
      path.startsWith("/students/me/connections")
    ) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: envelope({
          pending: [],
          access_state: "UNLINKED",
          linked_parents: [],
          link_history: [],
        }),
      });
      return;
    }

    if (method === "GET" && path === `/students/me/lectures/lec-m14`) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: envelope({
          lecture: {
            id: "lec-m14",
            title: "M-14 Live Feedback Lecture",
            topic: "Adaptation",
            status: "published",
          },
          session: {
            id: "sess-m14",
            lecture_id: "lec-m14",
            status: "active",
            mode: "text",
          },
          paragraphs: [
            {
              id: "p1",
              ordinal: 0,
              text: "Force equals mass times acceleration.",
              tier: "curriculum",
              book_name: null,
            },
          ],
        }),
      });
      return;
    }

    if (path.includes("/sessions/") && path.endsWith("/events") && method === "POST") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: envelope({ accepted: true, event_type: "page_change" }),
      });
      return;
    }

    if (path.includes("/sessions/") && path.endsWith("/touch")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: envelope({ id: "sess-m14", status: "active", mode: "text" }),
      });
      return;
    }

    if (path.includes("/questions") && method === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: envelope([]),
      });
      return;
    }

    if (path.includes("/privacy") || path.includes("/teacher-share")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: envelope({ teacher_activity_share: true }),
      });
      return;
    }

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: envelope({}),
    });
  });

  // Stub WebSocket: inject metrics after connect via page evaluation helper.
  await page.addInitScript(() => {
    class FakeWS {
      static OPEN = 1;
      readyState = 1;
      onmessage: ((ev: MessageEvent) => void) | null = null;
      onclose: (() => void) | null = null;
      onopen: (() => void) | null = null;
      constructor(public url: string) {
        queueMicrotask(() => {
          this.onopen?.(new Event("open") as unknown as void);
          // Simulate 2+ minutes activity + stuck nudge once.
          this.onmessage?.(
            new MessageEvent("message", {
              data: JSON.stringify({
                type: "live_feedback_update",
                payload: {
                  panel_visible: true,
                  time_on_topic_seconds: 150,
                  questions_asked_this_session: 0,
                  mastery_estimate: null,
                  daily_goal_status: null,
                  stuck_nudge: { should_show: true, seconds_on_page: 700 },
                },
              }),
            }),
          );
        });
      }
      send() {}
      close() {
        this.onclose?.();
      }
      addEventListener() {}
      removeEventListener() {}
    }
    // @ts-expect-error test double
    window.WebSocket = FakeWS;
  });
}

test.describe("M-14 live feedback smoke @smoke @mock", () => {
  test("panel appears and stuck nudge fires once", async ({ page }) => {
    await installMocks(page);
    await page.goto("/student/lectures/lec-m14");

    await expect(page.getByTestId("live-feedback-panel")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId("live-feedback-questions")).toHaveText("0");

    await expect(page.getByTestId("stuck-nudge")).toBeVisible();
    await page.getByTestId("stuck-nudge-dismiss").click();
    await expect(page.getByTestId("stuck-nudge")).toHaveCount(0);

    // Collapse persists in session storage key shape.
    await page.getByTestId("live-feedback-collapse").click();
    const collapsed = await page.evaluate(() =>
      sessionStorage.getItem("live-feedback-collapsed:sess-m14"),
    );
    expect(collapsed).toBe("1");
  });
});
