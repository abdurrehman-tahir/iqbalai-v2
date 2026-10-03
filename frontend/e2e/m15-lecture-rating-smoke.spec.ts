/**
 * T-192 — lecture rating acceptance path (@smoke @mock).
 * Student: completion (scroll to the end) → optional prompt → dismiss / rate.
 * Teacher: sees only the anonymous aggregate + the 95/5 blended quality score.
 */
import { expect, test, type Page, type Route } from "@playwright/test";
import {
  API_BASE,
  envelope,
  installStudentMocks,
  viewerPayload,
} from "./helpers/m15-mocks";

const LONG_TEXT = Array.from(
  { length: 40 },
  (_, i) => `Sentence ${i + 1} about forces.`,
).join(" ");

async function scrollToEnd(page: Page) {
  await page.evaluate(() =>
    window.scrollTo(0, document.documentElement.scrollHeight),
  );
  await page.mouse.wheel(0, 4000);
}

test.describe("M-15 lecture rating — student @smoke @mock", () => {
  test("prompt appears only after completion, can be dismissed, and a 1-5 rating is sent", async ({
    page,
  }) => {
    let submitted: unknown = null;
    await installStudentMocks(page, ({ method, path, body }) => {
      if (method === "POST" && path === "/students/me/lectures/lec-m15/open") {
        return viewerPayload(LONG_TEXT);
      }
      if (path === "/students/me/lectures/lec-m15/rating") {
        if (method === "PUT") {
          submitted = body;
          return {
            lecture_id: "lec-m15",
            rating: (body as { rating: number }).rating,
          };
        }
        return { lecture_id: "lec-m15", rating: null };
      }
      return undefined;
    });
    await page.setViewportSize({ width: 1280, height: 500 });

    await page.goto("/student/lectures/lec-m15");
    await expect(page.getByTestId("lecture-paragraph-text")).toBeVisible({
      timeout: 15_000,
    });
    // Not complete yet → no prompt.
    await expect(page.getByTestId("lecture-rating-prompt")).toHaveCount(0);

    await scrollToEnd(page);
    const prompt = page.getByTestId("lecture-rating-prompt");
    await expect(prompt).toBeVisible({ timeout: 10_000 });

    // Dismiss → gone, and stays gone for this lecture after reload.
    await prompt.getByTestId("lecture-rating-dismiss").click();
    await expect(page.getByTestId("lecture-rating-prompt")).toHaveCount(0);
    await page.reload();
    await expect(page.getByTestId("lecture-paragraph-text")).toBeVisible({
      timeout: 15_000,
    });
    await scrollToEnd(page);
    await page.waitForTimeout(500);
    await expect(page.getByTestId("lecture-rating-prompt")).toHaveCount(0);

    // A fresh session (dismissal cleared) → rate 4 stars.
    await page.evaluate(() => sessionStorage.clear());
    await page.reload();
    await expect(page.getByTestId("lecture-paragraph-text")).toBeVisible({
      timeout: 15_000,
    });
    await scrollToEnd(page);
    await page.getByRole("radio", { name: "4 stars" }).click();
    await page.getByTestId("lecture-rating-submit").click();
    await expect(page.getByText("Thanks for your rating!")).toBeVisible();
    expect(submitted).toEqual({ rating: 4 });
  });
});

const SCORED_VERSION = {
  id: "v-2",
  lecture_id: "lec-1",
  version: 2,
  content_jsonb: { type: "doc", content: [] },
  body: "Body.",
  scores_jsonb: { total: 44 },
  topic_relevance_pct: 88.0,
  originality_score: 0.8,
  edit_summary: [],
  created_at: "2026-08-05T00:05:00Z",
};

async function installTeacherMocks(
  page: Page,
  summary: Record<string, unknown>,
) {
  await page.route(`${API_BASE}/**`, async (route: Route) => {
    const url = new URL(route.request().url());
    let path = url.pathname.replace("/api/v1", "");
    if (path.length > 1 && path.endsWith("/")) path = path.slice(0, -1);
    const json = (data: unknown) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: envelope(data),
      });

    if (path === "/auth/me") {
      return json({
        user_id: "teacher-1",
        email: "teacher@test.com",
        role: "teacher",
        tenant_type: "school",
        school_id: "school-1",
        district_id: null,
      });
    }
    if (path === "/teachers/me/offerings") {
      return json([
        {
          id: "off-1",
          grade_id: "g-1",
          grade_name: "Grade 9",
          grade_level_ordinal: 9,
          subject_id: "s-1",
          subject_name: "Physics",
          academic_session: "2025-2026",
        },
      ]);
    }
    if (path === "/teachers/me/onboarding") {
      return json({
        state: "ready_to_teach",
        profile_complete: true,
        ready_to_teach: true,
        assignment_count: 1,
        can_create_content: true,
        teacher_capacity: 5,
        capacity_below_assignments: false,
        profile: null,
      });
    }
    if (path === "/teachers/me/lecture-draft") {
      return json({
        id: "draft-1",
        teacher_user_id: "teacher-1",
        step: 5,
        data: { lecture_id: "lec-1" },
        updated_at: "2026-08-05T00:00:00Z",
      });
    }
    if (path === "/teachers/me/lectures/lec-1/versions/current")
      return json(SCORED_VERSION);
    if (path === "/teachers/me/lectures/lec-1/versions") {
      return json({
        items: [SCORED_VERSION],
        total: 1,
        page: 1,
        page_size: 6,
        pages: 1,
      });
    }
    if (path === "/lectures/lec-1/rating-summary") return json(summary);
    if (
      path.endsWith("/paragraphs") ||
      path.endsWith("/links") ||
      path.endsWith("/quiz-results") ||
      path === "/teachers/me/coaching" ||
      path === "/teachers/me/benchmarks"
    ) {
      return json([]);
    }
    if (path.endsWith("/access"))
      return json({
        lecture_id: "lec-1",
        is_restricted: false,
        assignments: [],
      });
    if (path.endsWith("/teacher-tips"))
      return json({ lecture_id: "lec-1", status: "pending", tips: null });
    if (path.endsWith("/quiz-aggregate")) {
      return json({
        lecture_id: "lec-1",
        assigned_count: 0,
        completed_count: 0,
        completion_rate: 0,
        average_score: null,
        hotspots: [],
      });
    }
    if (path.endsWith("/diagram-suggestions")) return json({ suggestions: [] });
    return json({});
  });
  await page.routeWebSocket(/\/ws\/v1\/lectures\/.*\/generation/, (ws) => {
    ws.send(JSON.stringify({ type: "connected", id: "1", data: {}, meta: {} }));
    ws.send(
      JSON.stringify({
        type: "lecture_generation_complete",
        id: "2",
        data: { version_id: "v-2" },
        meta: {},
      }),
    );
  });
  await page.routeWebSocket(/\/ws\/v1\/lectures\/.*\/voice/, () => undefined);
}

test.describe("M-15 lecture rating — teacher @smoke @mock", () => {
  test("teacher sees anonymous average and the 95/5 blended quality score", async ({
    page,
  }) => {
    await installTeacherMocks(page, {
      lecture_id: "lec-1",
      rating_count: 3,
      min_ratings_for_display: 3,
      average_rating: 5,
      ai_score: 44,
      ai_score_max: 55,
      quality_score: 81,
      rating_weight: 0.05,
    });
    await page.goto("/teacher/lectures/new");
    const card = page.getByTestId("lecture-quality-summary");
    await expect(card).toBeVisible({ timeout: 20_000 });
    await expect(card.getByTestId("lecture-quality-score")).toHaveText(
      "81 / 100",
    );
    await expect(card.getByTestId("lecture-quality-ai")).toHaveText(
      "AI score: 44 / 55",
    );
    await expect(card.getByTestId("lecture-quality-rating")).toContainText(
      "5 / 5 (3 ratings)",
    );
    // Anonymous: no student identifiers anywhere in the card.
    await expect(card).not.toContainText("stu-");
  });

  test("average withheld below the anonymity threshold", async ({ page }) => {
    await installTeacherMocks(page, {
      lecture_id: "lec-1",
      rating_count: 1,
      min_ratings_for_display: 3,
      average_rating: null,
      ai_score: 44,
      ai_score_max: 55,
      quality_score: 80,
      rating_weight: 0.05,
    });
    await page.goto("/teacher/lectures/new");
    const rating = page.getByTestId("lecture-quality-rating");
    await expect(rating).toContainText(
      "the average appears once 3 students have rated",
      {
        timeout: 20_000,
      },
    );
  });
});
