/**
 * M-16 E2E test doubles (T-201…T-208). Route-level API mocks for the teacher
 * next-day review surfaces. LLM / NATS / Celery are never reached — every
 * backend call is answered here, and writes are recorded for assertions.
 */
import type { Page } from "@playwright/test";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export function envelope<T>(data: T) {
  return JSON.stringify({ data, message: "ok" });
}

export type Recorded = { method: string; path: string; body: unknown };

export const REVIEW_SUMMARY = {
  id: "rev-1",
  lecture_id: "lec-1",
  lecture_title: "Newton's Laws",
  offering_label: "Grade 9 Physics",
  review_date: "2026-10-22",
  generated_at: "2026-10-22T23:30:00Z",
  status: "pending",
  pending_action: true,
  dismissed_at: null,
  acted_actions: [] as string[],
  critical_count: 1,
  high_frequency_count: 1,
  read_only: false,
};

function cluster(ref: string, column: "critical" | "high_frequency") {
  return {
    cluster_ref: ref,
    lecture_id: "lec-1",
    column,
    question_count: 2,
    unique_student_count: 2,
    criticality: column === "critical" ? 8 : 3,
    representative_question: `Why do action and reaction forces not cancel (${ref})?`,
    mini_lecture_id: ref === "a" ? "mini-1" : null,
    skipped: false,
    questions: [
      {
        question_id: `${ref}-q0`,
        question_text: `Why don't the forces cancel? (${ref})`,
        student_user_id: "stu-0",
        student_name: "Ali Raza",
        paragraph_id: "p1",
        source_chunk_id: "c1",
        occurred_at: "2026-10-22T10:00:00Z",
      },
      {
        question_id: `${ref}-q1`,
        question_text: `Is the reaction smaller? (${ref})`,
        student_user_id: "stu-1",
        student_name: "Sara Khan",
        paragraph_id: "p1",
        source_chunk_id: "c1",
        occurred_at: "2026-10-22T10:05:00Z",
      },
    ],
  };
}

const LECTURE_VERSION = {
  id: "v-1",
  lecture_id: "lec-1",
  version: 1,
  content_jsonb: { type: "doc", content: [] },
  body: "Newton's third law: forces come in pairs.",
  scores_jsonb: null,
  topic_relevance_pct: null,
  originality_score: null,
  edit_summary: [],
  created_at: "2026-10-20T08:00:00Z",
};

export function reviewDetail(overrides: Record<string, unknown> = {}) {
  return {
    ...REVIEW_SUMMARY,
    ai_summary: "Students mixed up which body each force acts on.",
    reflective_prompt:
      "Would a worked example with everyday objects make the action-reaction pair more concrete?",
    reflected: false,
    mini_lecture_id: "mini-1",
    mini_preview: "Force pairs always act on two different bodies…",
    mini_published: false,
    critical: [cluster("a", "critical")],
    high_frequency: [cluster("b", "high_frequency")],
    replies: [],
    is_owner: true,
    can_act: true,
    ...overrides,
  };
}

/**
 * Install teacher-shell + review mocks. ``handler`` may answer any call first
 * (return non-undefined); every non-GET call is pushed onto ``recorded``.
 */
export async function installReviewMocks(
  page: Page,
  handler: (ctx: Recorded) => unknown | undefined = () => undefined,
): Promise<Recorded[]> {
  const recorded: Recorded[] = [];
  await page.route(`${API_BASE}/**`, async (route) => {
    const url = new URL(route.request().url());
    let path = url.pathname.replace("/api/v1", "");
    if (path.length > 1 && path.endsWith("/")) path = path.slice(0, -1);
    const method = route.request().method();
    let body: unknown = null;
    try {
      body = route.request().postDataJSON();
    } catch {
      body = route.request().postData();
    }
    if (method !== "GET") recorded.push({ method, path, body });

    const json = (data: unknown) =>
      route.fulfill({ status: 200, contentType: "application/json", body: envelope(data) });

    const custom = handler({ method, path, body });
    if (custom !== undefined) return json(custom);

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
    if (path === "/reviews" && method === "GET") return json([REVIEW_SUMMARY]);
    if (path === "/reviews/rev-1" && method === "GET") return json(reviewDetail());
    if (path === "/reviews/rev-1/reflection") return json(reviewDetail({ reflected: true }));
    if (path === "/reviews/rev-1/replies" || path === "/reviews/rev-1/skips") {
      return json(reviewDetail());
    }
    if (path === "/reviews/rev-1/regenerate-mini") return json(reviewDetail());
    if (path === "/reviews/rev-1/publish-mini") {
      return json(reviewDetail({ mini_published: true, status: "completed" }));
    }
    if (path === "/reviews/rev-1/dismiss") return json(reviewDetail({ status: "dismissed" }));
    if (path === "/reviews/rev-1/reopen" || path === "/reviews/rev-1/edit-main") {
      return json(reviewDetail());
    }
    if (path.startsWith("/notifications")) return json([]);
    // Flow 5 edit mode on /teacher/lectures/[id] (T-205 Edit Main Lecture).
    if (/^\/teachers\/me\/lectures\/[^/]+\/versions\/current$/.test(path)) {
      return json(LECTURE_VERSION);
    }
    if (/^\/teachers\/me\/lectures\/[^/]+\/versions$/.test(path)) {
      return json({ items: [LECTURE_VERSION], total: 1, page: 1, page_size: 6, pages: 1 });
    }
    if (path.endsWith("/paragraphs")) return json([]);
    if (path.endsWith("/diagram-suggestions")) return json({ suggestions: [] });
    return json({});
  });
  return recorded;
}
