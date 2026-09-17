/**
 * T-140 — M-10 milestone-closing E2E (Flow 5 §3.6-§3.12).
 *
 * AUTHORED, NOT RUNNABLE IN THIS DEV CONTAINER (Alpine/musl — Playwright's
 * browser binaries can't launch here; same pre-existing gap noted since
 * T-130's spec in lecture-wizard-smoke.spec.ts). CI runs this against the
 * composed staging stack per ARCH §12.23. The backend-side chained
 * equivalent — proving scoring -> benchmark -> admin metrics actually
 * connect, runnable in this environment — lives in
 * api/app/features/lectures/tests/test_m10_e2e_flow.py.
 *
 * Covers the school-tenant post-generation surfaces this milestone added:
 * score timeline (T-137), Teaching Innovation Record (T-138), anonymized
 * benchmark card (T-139 #37), and — via a second test — the admin
 * comparative metrics table + CSV export (T-139 #38). LLM/STT/embeddings
 * are mocked at the HTTP/WS boundary; the generation stream itself is
 * mocked via Playwright's WebSocket routing (no live network).
 */

import { test, expect, type Page, type Route } from "@playwright/test";

const BASE_URL = process.env.E2E_BASE_URL ?? "http://localhost:3000";

function envelope<T>(data: T) {
  return JSON.stringify({ data, message: "ok" });
}

function paginated<T>(items: T[]) {
  return JSON.stringify({
    data: { items, total: items.length, page: 1, page_size: 6, pages: 1 },
    message: "ok",
  });
}

const SCORED_VERSION = {
  id: "v-2",
  lecture_id: "lec-1",
  version: 2,
  content_jsonb: {
    type: "doc",
    content: [{ type: "paragraph", content: [{ type: "text", text: "Teacher-edited body." }] }],
  },
  body: "Teacher-edited body.",
  scores_jsonb: {
    originality: 8,
    depth: 7,
    cultural_relevance: 4,
    engagement: 4,
    alignment: 9,
    voice_quality: null,
    ai_learning: 6,
    total: 38,
  },
  topic_relevance_pct: 88.0,
  originality_score: 0.8,
  edit_summary: ["Added worked example"],
  created_at: "2026-08-05T00:05:00Z",
};

async function installScoredLectureMocks(page: Page) {
  await page.route(
    (url) => url.pathname.includes("/api/v1/") || url.pathname.includes("/auth/me"),
    async (route: Route) => {
      const request = route.request();
      const url = new URL(request.url());
      let path = url.pathname.replace("/api/v1", "");
      if (path.length > 1 && path.endsWith("/")) path = path.slice(0, -1);
      const method = request.method();

      if (method === "GET" && path === "/auth/me") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: envelope({
            user_id: "teacher-1",
            email: "teacher@test.com",
            role: "teacher",
            tenant_type: "school",
            school_id: "school-1",
            district_id: null,
          }),
        });
        return;
      }

      if (method === "GET" && path === "/teachers/me/offerings") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: envelope([
            {
              id: "off-1",
              grade_id: "g-1",
              grade_name: "Grade 9",
              grade_level_ordinal: 9,
              subject_id: "s-1",
              subject_name: "Physics",
              academic_session: "2025-2026",
            },
          ]),
        });
        return;
      }

      if (method === "GET" && path === "/teachers/me/onboarding") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: envelope({
            state: "ready_to_teach",
            profile_complete: true,
            ready_to_teach: true,
            assignment_count: 1,
            can_create_content: true,
            teacher_capacity: 5,
            capacity_below_assignments: false,
            profile: null,
          }),
        });
        return;
      }

      // Resume straight into the completed-generation view via the saved
      // draft — same shortcut the existing T-130 independent editor spec
      // uses, avoiding re-driving wizard steps 1–5 for a post-generation test.
      if (method === "GET" && path === "/teachers/me/lecture-draft") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: envelope({
            id: "draft-1",
            teacher_user_id: "teacher-1",
            step: 5,
            data: { lecture_id: "lec-1" },
            updated_at: "2026-08-05T00:00:00Z",
          }),
        });
        return;
      }

      if (method === "GET" && path === "/teachers/me/lectures/lec-1/paragraphs") {
        await route.fulfill({ status: 200, contentType: "application/json", body: envelope([]) });
        return;
      }

      if (method === "GET" && path === "/teachers/me/lectures/lec-1/versions/current") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: envelope(SCORED_VERSION),
        });
        return;
      }

      // T-137 — score timeline reads the paginated version list.
      if (method === "GET" && path === "/teachers/me/lectures/lec-1/versions") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: paginated([SCORED_VERSION]),
        });
        return;
      }

      // T-138 — Teaching Innovation Record: one pending coaching tip.
      if (method === "GET" && path === "/teachers/me/coaching") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: envelope([
            {
              id: "memory-1",
              weakness_type: "cultural_relevance",
              suggestion: "Try grounding examples in local Punjab context.",
              frequency: 2,
              updated_at: "2026-08-05T00:00:00Z",
            },
          ]),
        });
        return;
      }

      if (method === "GET" && path === "/teachers/me/lectures/lec-1/links") {
        await route.fulfill({ status: 200, contentType: "application/json", body: envelope([]) });
        return;
      }

      if (method === "GET" && path === "/teachers/me/lectures/lec-1/access") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: envelope({
            lecture_id: "lec-1",
            is_restricted: false,
            assignments: [],
          }),
        });
        return;
      }

      if (method === "GET" && path === "/teachers/me/lectures/lec-1/teacher-tips") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: envelope({ lecture_id: "lec-1", status: "pending", tips: null }),
        });
        return;
      }

      if (method === "GET" && path === "/teachers/me/lectures/lec-1/diagram-suggestions") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: envelope({ suggestions: [] }),
        });
        return;
      }

      if (method === "POST" && path === "/teachers/me/edit-sessions") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: envelope({
            id: "effort-session-1",
            active_ms: 0,
            edits_count: 0,
            char_delta: 0,
            started_at: "2026-08-05T00:00:00Z",
            ended_at: null,
            effort_score: 0,
          }),
        });
        return;
      }

      // T-139 #37 — anonymized benchmark: positively-framed standing only.
      if (method === "GET" && path === "/teachers/me/benchmarks") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: envelope([
            {
              id: "bm-1",
              subject_name: "Physics",
              grade_range: "9",
              region: "Punjab",
              top_percent: 23,
            },
          ]),
        });
        return;
      }

      await route.fulfill({ status: 200, contentType: "application/json", body: envelope({}) });
    }
  );

  // Generation stream: fire "connected" then immediately "complete" so the
  // wizard's GenerationStreamPanel resolves into its post-score view.
  await page.routeWebSocket(/\/ws\/v1\/lectures\/.*\/generation/, (ws) => {
    ws.send(
      JSON.stringify({
        type: "connected",
        id: "1",
        data: {},
        meta: { timestamp: "2026-08-05T00:05:00Z", request_id: null },
      })
    );
    ws.send(
      JSON.stringify({
        type: "lecture_generation_complete",
        id: "2",
        data: { version_id: "v-2" },
        meta: { timestamp: "2026-08-05T00:05:01Z", request_id: null },
      })
    );
  });
  // Voice conversation panel opens its own socket — a no-op mock is enough
  // so it doesn't hang retrying against a real server.
  await page.routeWebSocket(/\/ws\/v1\/lectures\/.*\/voice/, () => {});
}

test.describe("Lecture scoring, coaching, and benchmark surfaces @smoke (T-140)", () => {
  test("teacher sees the score timeline, a coaching tip, and their benchmark standing", async ({
    page,
  }) => {
    await installScoredLectureMocks(page);
    await page.goto(`${BASE_URL}/teacher/lectures/new`);

    await expect(page.getByRole("heading", { name: /Lecture ready/i })).toBeVisible({
      timeout: 15_000,
    });

    // T-138 — coaching suggestion, no score/number ever in its text.
    await expect(page.getByText("Try grounding examples in local Punjab context.")).toBeVisible();

    // T-139 #37 — positively-framed benchmark line.
    await expect(page.getByText(/Top 23% of Physics teachers in Punjab/i)).toBeVisible();

    // T-137 — score timeline renders the scored version (an SVG chart, not
    // text-queryable per-point — assert the chart container mounted).
    await expect(page.getByText(/Score Timeline/i)).toBeVisible();
  });
});

async function installAdminMetricsMocks(page: Page) {
  await page.route(
    (url) => url.pathname.includes("/api/v1/") || url.pathname.includes("/auth/me"),
    async (route: Route) => {
      const request = route.request();
      const url = new URL(request.url());
      let path = url.pathname.replace("/api/v1", "");
      if (path.length > 1 && path.endsWith("/")) path = path.slice(0, -1);
      const method = request.method();

      if (method === "GET" && path === "/auth/me") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: envelope({
            user_id: "admin-1",
            email: "admin@test.com",
            role: "school_admin",
            tenant_type: "school",
            school_id: "school-1",
            district_id: null,
          }),
        });
        return;
      }

      // T-139 #38 — admin comparative metrics, real names (not anonymized).
      if (method === "GET" && path === "/admin/teacher-metrics") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: envelope([
            {
              teacher_user_id: "teacher-1",
              teacher_name: "Ayesha Khan",
              school_id: "school-1",
              school_name: "Model School",
              subject_id: "subj-1",
              subject_name: "Physics",
              grade_range: "9",
              lecture_count: 3,
              avg_originality: 8,
              avg_depth: 7,
              avg_cultural_relevance: 4,
              avg_engagement: 4,
              avg_alignment: 9,
              avg_voice_quality: null,
              avg_ai_learning: 6,
              avg_total: 38,
              avg_topic_relevance_pct: 88,
            },
          ]),
        });
        return;
      }

      await route.fulfill({ status: 200, contentType: "application/json", body: envelope({}) });
    }
  );
}

test.describe("Admin comparative teacher metrics @smoke (T-140, #38)", () => {
  test("school admin sees the comparative metrics table with real teacher names", async ({
    page,
  }) => {
    await installAdminMetricsMocks(page);
    await page.goto(`${BASE_URL}/school/admin/teacher-metrics`);

    await expect(page.getByRole("heading", { name: /Teacher Metrics/i })).toBeVisible();
    await expect(page.getByText("Ayesha Khan")).toBeVisible();
    await expect(page.getByText("Model School")).toBeVisible();
    await expect(page.getByRole("button", { name: /Export CSV/i })).toBeVisible();
  });
});
