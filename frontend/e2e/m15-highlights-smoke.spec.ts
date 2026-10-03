/**
 * T-185 — highlight persistence + yellow-mark restore (@smoke @mock).
 * Backend is route-mocked; the mocks emulate the server-side anchor check
 * (mark=null once the span no longer maps — flow-6 §5.5).
 */
import { expect, test } from "@playwright/test";
import {
  installStudentMocks,
  PARA_TEXT,
  selectInParagraph,
  viewerPayload,
} from "./helpers/m15-mocks";

const OFFSET = PARA_TEXT.indexOf("mass");

function persisted(markVisible: boolean) {
  return {
    id: "h-1",
    lecture_id: "lec-m15",
    lecture_version_id: "ver-m15",
    paragraph_ordinal: 0,
    text_range_offset: OFFSET,
    text_range_length: 4,
    highlighted_text: "mass",
    question_id: "q-1",
    concept_tag: "forces/newton-2",
    tenant_type: "school",
    created_at: "2026-10-03T12:00:00Z",
    mark: markVisible
      ? { paragraph_id: "p1", offset: OFFSET, length: 4 }
      : null,
  };
}

test.describe("M-15 highlight persistence @smoke @mock", () => {
  test("highlight + ask persists the anchor and the yellow mark is restored", async ({
    page,
  }) => {
    let askBody: Record<string, unknown> | null = null;
    let saved = false;

    await installStudentMocks(page, ({ method, path, body }) => {
      if (
        method === "POST" &&
        path === "/students/me/lectures/lec-m15/sessions/sess-m15/questions"
      ) {
        askBody = body as Record<string, unknown>;
        saved = true;
        return {
          id: "q-1",
          student_user_id: "stu-1",
          session_id: "sess-m15",
          lecture_id: "lec-m15",
          tenant_type: "school",
          highlight_text: "mass",
          question_text: "Explain: mass",
          question_language: "en",
          paragraph_id: "p1",
          source_chunk_id: null,
          classification: "knowledge_gap",
          answer_text: "Mass is the amount of matter.",
          answer_source_tags_jsonb: null,
          attached_images: [],
          asked_at: "2026-10-03T12:00:00Z",
          answered_at: "2026-10-03T12:00:01Z",
          conversations: [],
        };
      }
      if (
        method === "GET" &&
        path === "/students/me/lectures/lec-m15/highlights"
      ) {
        return saved ? [persisted(true)] : [];
      }
      return undefined;
    });

    await page.goto("/student/lectures/lec-m15");
    await expect(page.getByTestId("lecture-paragraph-text")).toHaveText(
      PARA_TEXT,
      {
        timeout: 15_000,
      },
    );
    await expect(page.getByTestId("highlight-mark")).toHaveCount(0);

    await selectInParagraph(page, "mass");
    await expect(page.getByTestId("highlight-question-box")).toBeVisible();

    // The 3s auto-send fires the ask request.
    await expect.poll(() => askBody, { timeout: 10_000 }).not.toBeNull();
    expect(askBody).toMatchObject({
      highlight_text: "mass",
      highlight_offset: OFFSET,
      paragraph_id: "p1",
    });

    // Highlights are refetched after asking → the yellow mark appears.
    await expect(page.getByTestId("highlight-mark")).toHaveText("mass", {
      timeout: 10_000,
    });

    // Returning to the lecture restores the mark at its original position.
    await page.reload();
    await expect(page.getByTestId("highlight-mark")).toHaveText("mass", {
      timeout: 15_000,
    });
  });

  test("re-edited lecture drops the mark silently", async ({ page }) => {
    const edited = "Force is a push or a pull acting on an object.";
    await installStudentMocks(page, ({ method, path }) => {
      if (method === "POST" && path === "/students/me/lectures/lec-m15/open") {
        return viewerPayload(edited);
      }
      if (
        method === "GET" &&
        path === "/students/me/lectures/lec-m15/highlights"
      ) {
        return [persisted(false)];
      }
      return undefined;
    });

    await page.goto("/student/lectures/lec-m15");
    await expect(page.getByTestId("lecture-paragraph-text")).toHaveText(
      edited,
      {
        timeout: 15_000,
      },
    );
    await expect(page.getByTestId("highlight-mark")).toHaveCount(0);
    await expect(page.getByTestId("lecture-viewer-error")).toHaveCount(0);
  });
});
