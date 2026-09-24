/**
 * T-154 — Student lecture viewer + karaoke voice mode (@smoke @mock).
 */
import { test, expect, type Page, type Route } from "@playwright/test";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

function envelope<T>(data: T) {
  return JSON.stringify({ data, message: "ok" });
}

async function installMocks(page: Page) {
  let mode: "text" | "voice" = "text";

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
        body: envelope({
          pending: [],
          access_state: "UNLINKED",
          linked_parents: [],
          link_history: [],
        }),
      });
      return;
    }

    if (method === "GET" && path === "/students/me/lectures") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: envelope([
          {
            lecture_id: "lec-1",
            title: "Newton's Laws",
            topic: "Forces",
            current_version_id: "ver-1",
          },
        ]),
      });
      return;
    }

    if (method === "GET" && path === "/students/me/quizzes") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: envelope([]),
      });
      return;
    }

    if (method === "POST" && path === "/students/me/lectures/lec-1/open") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: envelope({
          lecture_id: "lec-1",
          title: "Newton's Laws",
          topic: "Forces",
          current_version_id: "ver-1",
          language: null,
          session: {
            id: "sess-1",
            lecture_id: "lec-1",
            student_user_id: "stu-1",
            tenant_type: "school",
            mode,
            status: "active",
            opened_at: "2026-09-21T12:00:00Z",
            last_activity_at: "2026-09-21T12:00:00Z",
            ended_at: null,
          },
          paragraphs: [
            {
              id: "p1",
              ordinal: 0,
              text: "Force equals mass times acceleration.",
              tier: "curriculum",
              book_name: null,
              source_url: null,
            },
          ],
        }),
      });
      return;
    }

    if (method === "PATCH" && path === "/students/me/lectures/sessions/sess-1/mode") {
      const body = route.request().postDataJSON() as { mode: "text" | "voice" };
      mode = body.mode;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: envelope({
          id: "sess-1",
          lecture_id: "lec-1",
          student_user_id: "stu-1",
          tenant_type: "school",
          mode,
          status: "active",
          opened_at: "2026-09-21T12:00:00Z",
          last_activity_at: "2026-09-21T12:00:00Z",
          ended_at: null,
        }),
      });
      return;
    }

    if (method === "POST" && path === "/students/me/lectures/sessions/sess-1/activity") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: envelope({
          id: "sess-1",
          lecture_id: "lec-1",
          student_user_id: "stu-1",
          tenant_type: "school",
          mode,
          status: "active",
          opened_at: "2026-09-21T12:00:00Z",
          last_activity_at: "2026-09-21T12:01:00Z",
          ended_at: null,
        }),
      });
      return;
    }

    if (
      (method === "POST" && path === "/students/me/lectures/lec-1/audio") ||
      (method === "GET" && path === "/students/me/lectures/lec-1/audio/en")
    ) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: envelope({
          id: "aud-1",
          lecture_id: "lec-1",
          lecture_version_id: "ver-1",
          language: "en",
          status: "ready",
          audio_url: "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAESsAACJWAAACABAAZGF0YQAAAAA=",
          duration_ms: 1000,
          alignment: [
            {
              ordinal: 0,
              paragraph_id: "p1",
              text: "Force equals mass times acceleration.",
              start_ms: 0,
              end_ms: 1000,
            },
          ],
        }),
      });
      return;
    }

    if (method === "GET" && path === "/students/me/lectures/lec-1/questions") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: envelope([]),
      });
      return;
    }

    if (method === "POST" && path === "/students/me/lectures/lec-1/sessions/sess-1/questions") {
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: envelope({
          id: "q-1",
          student_user_id: "stu-1",
          session_id: "sess-1",
          lecture_id: "lec-1",
          tenant_type: "school",
          highlight_text: "Force equals mass",
          question_text: "Explain: Force equals mass",
          question_language: "en",
          paragraph_id: "p1",
          source_chunk_id: null,
          classification: "knowledge_gap",
          answer_text: null,
          answer_source_tags_jsonb: null,
          asked_at: "2026-09-21T12:02:00Z",
          answered_at: null,
          conversations: [
            {
              id: "t0",
              root_question_id: "q-1",
              turn_index: 0,
              role: "user",
              content: "Explain: Force equals mass",
              source_tags_jsonb: null,
              created_at: "2026-09-21T12:02:00Z",
            },
          ],
        }),
      });
      return;
    }

    if (method === "GET" && path === "/students/me/lectures/lec-1/questions/q-1/answer/stream") {
      await route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body: "data: Force is mass times acceleration [Curriculum]\n\ndata: [DONE]\n\n",
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

test.describe("M-12 lecture viewer karaoke @smoke @mock", () => {
  test("dashboard → open lecture → voice toggle → karaoke controls", async ({ page }) => {
    await installMocks(page);
    await page.goto("/student");
    await expect(page.getByTestId("student-lectures")).toBeVisible();
    await page.getByRole("link", { name: /open/i }).first().click();
    await expect(page.getByTestId("lecture-viewer")).toBeVisible();
    await expect(page.getByTestId("source-badge").first()).toBeVisible();
    await page.getByTestId("voice-mode-toggle").click();
    await expect(page.getByTestId("karaoke-player")).toBeVisible();
    await expect(page.getByTestId("karaoke-play-pause")).toBeVisible();
    await expect(page.getByTestId("karaoke-seek-back")).toBeVisible();
    await expect(page.getByTestId("karaoke-download")).toBeVisible();
  });

  test("questions tab renders empty state (T-160)", async ({ page }) => {
    await installMocks(page);
    await page.goto("/student/lectures/lec-1");
    await expect(page.getByTestId("lecture-viewer")).toBeVisible();
    await expect(page.getByTestId("questions-tab")).toBeVisible();
    await expect(page.getByTestId("questions-empty")).toBeVisible();
  });
});
