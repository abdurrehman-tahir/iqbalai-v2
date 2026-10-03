/**
 * M-15 E2E test doubles (T-185…T-194). Route-level API mocks for the student
 * lecture viewer + My Highlights + concept enrichment + rating surfaces.
 * LLM / NATS are never reached — every backend call is answered here.
 */
import type { Page, Route } from "@playwright/test";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export const PARA_TEXT =
  "Force equals mass times acceleration. Newton's second law links them.";

export function envelope<T>(data: T) {
  return JSON.stringify({ data, message: "ok" });
}

export type JsonHandler = (ctx: {
  method: string;
  path: string;
  body: unknown;
  route: Route;
}) => unknown | undefined;

const SESSION = {
  id: "sess-m15",
  lecture_id: "lec-m15",
  student_user_id: "stu-1",
  tenant_type: "school",
  mode: "text",
  status: "active",
  opened_at: "2026-10-03T12:00:00Z",
  last_activity_at: "2026-10-03T12:00:00Z",
  ended_at: null,
};

export function viewerPayload(paragraphText = PARA_TEXT) {
  return {
    lecture_id: "lec-m15",
    title: "Newton's Laws",
    topic: "Forces",
    current_version_id: "ver-m15",
    language: null,
    session: SESSION,
    paragraphs: [
      {
        id: "p1",
        ordinal: 0,
        text: paragraphText,
        tier: "curriculum",
        book_name: null,
        source_url: null,
      },
    ],
  };
}

/**
 * Install the baseline student mocks. `handler` runs first for every API
 * request; return a value to answer with `envelope(value)` (status 200), or
 * `undefined` to fall through to the defaults.
 */
export async function installStudentMocks(
  page: Page,
  handler: JsonHandler = () => undefined,
  opts: { role?: string } = {},
) {
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

    const custom = handler({ method, path, body, route });
    if (custom !== undefined) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: envelope(custom),
      });
      return;
    }

    const json = (data: unknown) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: envelope(data),
      });

    if (method === "GET" && path === "/auth/me") {
      return json({
        user_id: "stu-1",
        email: "student@example.com",
        role: opts.role ?? "student",
        tenant_type: "school",
        school_id: "school-1",
        district_id: null,
      });
    }
    if (path === "/students/me/onboarding") {
      return json({
        ready_to_study: true,
        show_complete_profile_banner: false,
      });
    }
    if (path === "/students/me/mode") {
      return json({
        active_mode: "lecture",
        mode_state: { lecture: {}, self_study: {} },
        lecture_mode_enabled: true,
        self_study_mode_enabled: true,
      });
    }
    if (
      path.startsWith("/students/me/link-requests") ||
      path.startsWith("/students/me/connections")
    ) {
      return json({
        pending: [],
        access_state: "UNLINKED",
        linked_parents: [],
        link_history: [],
      });
    }
    if (method === "POST" && path === "/students/me/lectures/lec-m15/open") {
      return json(viewerPayload());
    }
    if (path.includes("/sessions/") && path.endsWith("/events")) {
      return json({ accepted: true, event_type: "page_change" });
    }
    if (
      path.includes("/sessions/") &&
      (path.endsWith("/activity") || path.endsWith("/end"))
    ) {
      return json(SESSION);
    }
    if (method === "GET" && path.endsWith("/questions")) return json([]);
    if (method === "GET" && path.endsWith("/highlights")) return json([]);
    if (path.includes("/privacy") || path.includes("/teacher-share")) {
      return json({ teacher_activity_share: "share" });
    }
    return json({});
  });

  // Live-feedback socket (M-14) — stays quiet in M-15 specs.
  await page.routeWebSocket(/\/ws\/v1\/live-feedback/, () => undefined);
}

/** Select `text` inside the first lecture paragraph and fire the viewer's mouseup. */
export async function selectInParagraph(page: Page, text: string) {
  await page.evaluate((needle) => {
    const el = document.querySelector('[data-testid="lecture-paragraph-text"]');
    if (!el) throw new Error("paragraph text not found");
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    let node = walker.nextNode();
    while (node) {
      const idx = (node.textContent ?? "").indexOf(needle);
      if (idx >= 0) {
        const range = document.createRange();
        range.setStart(node, idx);
        range.setEnd(node, idx + needle.length);
        const sel = window.getSelection();
        sel?.removeAllRanges();
        sel?.addRange(range);
        el.dispatchEvent(new MouseEvent("mouseup", { bubbles: true }));
        return;
      }
      node = walker.nextNode();
    }
    throw new Error(`text not found: ${needle}`);
  }, text);
}
