/**
 * T-172 — Hybrid widget + vision Q&A E2E smoke (@smoke @mock).
 *
 * Exercises the ONE canonical `HybridInputWidget` (T-155/T-171 reuse contract)
 * as mounted on the two M-13 lecture Q&A surfaces:
 *   - `HighlightQuestionBox` (ask a new question, `allowImages`)
 *   - `AnswerSidePanel` (follow-up on an existing question, `allowImages`)
 *
 * Covers (per the M-13 backlog T-172 acceptance list): icon attach, drag,
 * paste, thumbnails, remove, the 3-image cap, oversize (>5MB) rejection, GIF
 * (unsupported format) rejection, a text+image submit with `attached_images`
 * storage keys threaded to the backend (the E2E-observable proxy for
 * server-side vision routing — actual LLM routing is covered by the T-168
 * backend unit tests), a text-only submit that omits `attached_images`
 * entirely, a follow-up with an image, and that exactly one
 * `hybrid-input-widget` is ever mounted at a time (no duplicate component).
 *
 * NOTE: live microphone capture is not exercised here (no reliable
 * getUserMedia/MediaRecorder fake-media harness exists in this repo's e2e
 * suite yet) — voice transcription writes into the same widget `text` state
 * that typing does (see `useVoiceTranscription`'s `mergeVoiceIntoText`), so
 * the "text + voice + image" submit path is exercised end-to-end here via
 * its text+image form; the voice-specific transcription plumbing itself is
 * covered by the HybridInputWidget Vitest/RTL suite.
 */
import { test, expect, type Page, type Route } from "@playwright/test";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

function envelope<T>(data: T) {
  return JSON.stringify({ data, message: "ok" });
}

// A valid, tiny (67-byte) 1x1 transparent PNG — well under the 5MB cap and an
// allowed mime type, so it exercises the "happy path" upload calls below.
const TINY_PNG_BASE64 =
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=";

type Calls = {
  uploads: Array<{ mimeType: string; size: number }>;
  askBodies: Array<Record<string, unknown>>;
  followUpBodies: Array<Record<string, unknown>>;
};

function freshCalls(): Calls {
  return { uploads: [], askBodies: [], followUpBodies: [] };
}

async function installMocks(page: Page, calls: Calls) {
  let uploadCounter = 0;

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

    if (method === "GET" && path === "/students/me/lectures") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: envelope([
          { lecture_id: "lec-1", title: "Newton's Laws", topic: "Forces", current_version_id: "ver-1" },
        ]),
      });
      return;
    }

    if (method === "GET" && path === "/students/me/quizzes") {
      await route.fulfill({ status: 200, contentType: "application/json", body: envelope([]) });
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
            mode: "text",
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

    if (method === "POST" && path === "/students/me/lectures/sessions/sess-1/activity") {
      await route.fulfill({ status: 200, contentType: "application/json", body: envelope({}) });
      return;
    }

    if (method === "GET" && path === "/students/me/lectures/lec-1/questions") {
      await route.fulfill({ status: 200, contentType: "application/json", body: envelope([]) });
      return;
    }

    // Image upload (T-166/T-167).
    if (method === "POST" && path === "/students/me/question-images") {
      uploadCounter += 1;
      const contentType = route.request().headers()["content-type"] ?? "";
      const postBody = route.request().postDataBuffer();
      calls.uploads.push({ mimeType: contentType, size: postBody?.length ?? 0 });
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: envelope({
          upload_id: `up-${uploadCounter}`,
          storage_key: `student-question-image/school-1/2026/01/01/up-${uploadCounter}/img.png`,
          mime_type: "image/png",
          size_bytes: postBody?.length ?? 0,
          retention_days: 365,
        }),
      });
      return;
    }

    // New question (HighlightQuestionBox → studentQuestionsApi.ask).
    if (method === "POST" && path === "/students/me/lectures/lec-1/sessions/sess-1/questions") {
      const body = (route.request().postDataJSON() ?? {}) as Record<string, unknown>;
      calls.askBodies.push(body);
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: envelope({
          id: "q-1",
          student_user_id: "stu-1",
          session_id: "sess-1",
          lecture_id: "lec-1",
          tenant_type: "school",
          highlight_text: body.highlight_text ?? "",
          question_text: body.question_text ?? "",
          question_language: "en",
          paragraph_id: body.paragraph_id ?? null,
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
              content: body.question_text ?? "",
              source_tags_jsonb: null,
              created_at: "2026-09-21T12:02:00Z",
            },
          ],
        }),
      });
      return;
    }

    // Follow-up turn (AnswerSidePanel → studentQuestionsApi.followUp).
    if (method === "POST" && path === "/students/me/lectures/lec-1/questions/q-1/turns") {
      const body = (route.request().postDataJSON() ?? {}) as Record<string, unknown>;
      calls.followUpBodies.push(body);
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: envelope({
          id: "q-1",
          student_user_id: "stu-1",
          session_id: "sess-1",
          lecture_id: "lec-1",
          tenant_type: "school",
          highlight_text: "",
          question_text: "Force equals mass",
          question_language: "en",
          paragraph_id: "p1",
          source_chunk_id: null,
          classification: "knowledge_gap",
          answer_text: "Force is mass times acceleration.",
          answer_source_tags_jsonb: null,
          asked_at: "2026-09-21T12:02:00Z",
          answered_at: "2026-09-21T12:02:05Z",
          conversations: [
            {
              id: "t0",
              root_question_id: "q-1",
              turn_index: 0,
              role: "user",
              content: "Force equals mass",
              source_tags_jsonb: null,
              created_at: "2026-09-21T12:02:00Z",
            },
            {
              id: "t1",
              root_question_id: "q-1",
              turn_index: 1,
              role: "user",
              content: (body.content as string) ?? "",
              source_tags_jsonb: null,
              created_at: "2026-09-21T12:02:10Z",
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

    await route.fulfill({ status: 200, contentType: "application/json", body: envelope({}) });
  });
}

/** Selects the whole paragraph's text and fires the mouseup the viewer listens on. */
async function selectParagraphText(page: Page) {
  await page.evaluate(() => {
    const p = document.querySelector('[data-testid="lecture-paragraph"]');
    if (!p) throw new Error("lecture-paragraph not found");
    const range = document.createRange();
    range.selectNodeContents(p);
    const sel = window.getSelection();
    sel?.removeAllRanges();
    sel?.addRange(range);
  });
  await page.getByTestId("lecture-paragraphs").dispatchEvent("mouseup");
  await expect(page.getByTestId("highlight-question-box")).toBeVisible();
  // Cancel the 3s auto-send countdown deterministically (re-typing the
  // prefilled text triggers the same onChange→cancelAutoSend() path a real
  // keystroke would) so attach/drag/paste interactions below are never
  // racing the auto-submit timer.
  const textInput = page.getByTestId("hybrid-text-input");
  const current = await textInput.inputValue();
  await textInput.fill(`${current} `);
}

async function openLecture(page: Page) {
  await page.goto("/student/lectures/lec-1");
  await expect(page.getByTestId("lecture-viewer")).toBeVisible();
}

test.describe("M-13 hybrid widget + vision Q&A @smoke @mock", () => {
  test("attaches an image via the icon, shows a thumbnail, and can be removed", async ({ page }) => {
    const calls = freshCalls();
    await installMocks(page, calls);
    await openLecture(page);
    await selectParagraphText(page);

    await page.getByTestId("hybrid-image-input").setInputFiles({
      name: "diagram.png",
      mimeType: "image/png",
      buffer: Buffer.from(TINY_PNG_BASE64, "base64"),
    });

    await expect(page.getByTestId("hybrid-image-chip")).toBeVisible();
    expect(calls.uploads).toHaveLength(1);

    await page.getByRole("button", { name: /remove/i }).click();
    await expect(page.getByTestId("hybrid-image-chip")).not.toBeVisible();
  });

  test("rejects an oversized image and a GIF without ever calling the upload endpoint", async ({
    page,
  }) => {
    const calls = freshCalls();
    await installMocks(page, calls);
    await openLecture(page);
    await selectParagraphText(page);

    // >5MB — rejected client-side by useImageUpload before any network call.
    await page.getByTestId("hybrid-image-input").setInputFiles({
      name: "huge.png",
      mimeType: "image/png",
      buffer: Buffer.alloc(6 * 1024 * 1024, 1),
    });
    await expect(page.getByTestId("hybrid-error")).toBeVisible();
    expect(calls.uploads).toHaveLength(0);

    // Unsupported format (GIF) — also rejected client-side.
    await page.getByTestId("hybrid-image-input").setInputFiles({
      name: "animated.gif",
      mimeType: "image/gif",
      buffer: Buffer.from(TINY_PNG_BASE64, "base64"),
    });
    await expect(page.getByTestId("hybrid-error")).toBeVisible();
    expect(calls.uploads).toHaveLength(0);
    await expect(page.getByTestId("hybrid-image-chip")).not.toBeVisible();
  });

  test("enforces the 3-image cap", async ({ page }) => {
    const calls = freshCalls();
    await installMocks(page, calls);
    await openLecture(page);
    await selectParagraphText(page);

    const input = page.getByTestId("hybrid-image-input");
    for (const name of ["a.png", "b.png", "c.png"]) {
      await input.setInputFiles({
        name,
        mimeType: "image/png",
        buffer: Buffer.from(TINY_PNG_BASE64, "base64"),
      });
      await expect(page.getByTestId("hybrid-image-chip").nth(0)).toBeVisible();
    }
    await expect(page.getByTestId("hybrid-image-chip")).toHaveCount(3);
    await expect(page.getByTestId("hybrid-image-button")).toBeDisabled();
    expect(calls.uploads).toHaveLength(3);
  });

  test("drag-and-drop onto the widget attaches an image", async ({ page }) => {
    const calls = freshCalls();
    await installMocks(page, calls);
    await openLecture(page);
    await selectParagraphText(page);

    await page.evaluate((base64) => {
      const widget = document.querySelector('[data-testid="hybrid-input-widget"]');
      if (!widget) throw new Error("hybrid-input-widget not found");
      const byteChars = atob(base64);
      const bytes = new Uint8Array(byteChars.length);
      for (let i = 0; i < byteChars.length; i += 1) bytes[i] = byteChars.charCodeAt(i);
      const file = new File([bytes], "dropped.png", { type: "image/png" });
      const dataTransfer = new DataTransfer();
      dataTransfer.items.add(file);
      const dropEvent = new Event("drop", { bubbles: true, cancelable: true });
      Object.defineProperty(dropEvent, "dataTransfer", { value: dataTransfer });
      widget.dispatchEvent(dropEvent);
    }, TINY_PNG_BASE64);

    await expect(page.getByTestId("hybrid-image-chip")).toBeVisible();
    expect(calls.uploads).toHaveLength(1);
  });

  test("pasting a clipboard image attaches it", async ({ page }) => {
    const calls = freshCalls();
    await installMocks(page, calls);
    await openLecture(page);
    await selectParagraphText(page);

    await page.evaluate((base64) => {
      const widget = document.querySelector('[data-testid="hybrid-input-widget"]');
      if (!widget) throw new Error("hybrid-input-widget not found");
      const byteChars = atob(base64);
      const bytes = new Uint8Array(byteChars.length);
      for (let i = 0; i < byteChars.length; i += 1) bytes[i] = byteChars.charCodeAt(i);
      const file = new File([bytes], "pasted.png", { type: "image/png" });
      const pasteEvent = new Event("paste", { bubbles: true, cancelable: true });
      Object.defineProperty(pasteEvent, "clipboardData", {
        value: {
          items: [
            {
              kind: "file",
              type: "image/png",
              getAsFile: () => file,
            },
          ],
        },
      });
      widget.dispatchEvent(pasteEvent);
    }, TINY_PNG_BASE64);

    await expect(page.getByTestId("hybrid-image-chip")).toBeVisible();
    expect(calls.uploads).toHaveLength(1);
  });

  test("text+image submit threads attached_images to the ask request (vision routing signal)", async ({
    page,
  }) => {
    const calls = freshCalls();
    await installMocks(page, calls);
    await openLecture(page);
    await selectParagraphText(page);

    await page.getByTestId("hybrid-image-input").setInputFiles({
      name: "diagram.png",
      mimeType: "image/png",
      buffer: Buffer.from(TINY_PNG_BASE64, "base64"),
    });
    await expect(page.getByTestId("hybrid-image-chip")).toBeVisible();

    await page.getByTestId("hybrid-send-button").click();

    await expect(page.getByTestId("answer-side-panel")).toBeVisible();
    await expect.poll(() => calls.askBodies.length).toBe(1);
    const askBody = calls.askBodies[0];
    expect(Array.isArray(askBody.attached_images)).toBe(true);
    expect((askBody.attached_images as string[]).length).toBe(1);
  });

  test("text-only submit omits attached_images entirely (stays on the text model)", async ({
    page,
  }) => {
    const calls = freshCalls();
    await installMocks(page, calls);
    await openLecture(page);
    await selectParagraphText(page);

    await page.getByTestId("hybrid-send-button").click();

    await expect(page.getByTestId("answer-side-panel")).toBeVisible();
    await expect.poll(() => calls.askBodies.length).toBe(1);
    expect(calls.askBodies[0].attached_images).toBeUndefined();
  });

  test("follow-up with an image threads attached_images, and only one widget is mounted", async ({
    page,
  }) => {
    const calls = freshCalls();
    await installMocks(page, calls);
    await openLecture(page);
    await selectParagraphText(page);

    // Ask the initial (text-only) question to open the answer panel.
    await page.getByTestId("hybrid-send-button").click();
    await expect(page.getByTestId("answer-side-panel")).toBeVisible();

    // The highlight box unmounts once a question is created — exactly one
    // canonical HybridInputWidget remains mounted (T-171 reuse contract).
    await expect(page.getByTestId("hybrid-input-widget")).toHaveCount(1);

    await page.getByTestId("hybrid-image-input").setInputFiles({
      name: "followup.png",
      mimeType: "image/png",
      buffer: Buffer.from(TINY_PNG_BASE64, "base64"),
    });
    await expect(page.getByTestId("hybrid-image-chip")).toBeVisible();

    await page.getByTestId("hybrid-text-input").fill("What about the diagram?");
    await page.getByTestId("hybrid-send-button").click();

    await expect.poll(() => calls.followUpBodies.length).toBe(1);
    const followUpBody = calls.followUpBodies[0];
    expect(Array.isArray(followUpBody.attached_images)).toBe(true);
    expect((followUpBody.attached_images as string[]).length).toBe(1);
    await expect(page.getByTestId("hybrid-input-widget")).toHaveCount(1);
  });
});
