/**
 * T-194 — M-15 full student journey through the real UI (@smoke @mock).
 * A stateful route-level mock backend (no LLM, no network) carries state
 * across pages: highlight+ask → mark → concept card (cache miss → ready) →
 * mini-sim saved & restored → My Highlights (paired flashcard) → completion
 * rating → Urdu/RTL rendering. The real-backend chained equivalent is
 * api/tests/test_m15_e2e_flow.py.
 */
import { expect, test, type Page } from "@playwright/test";
import {
  installStudentMocks,
  selectInParagraph,
  viewerPayload,
} from "./helpers/m15-mocks";

const TEXT = Array.from({ length: 30 }, (_, i) =>
  i === 0
    ? "Force equals mass times acceleration."
    : `Sentence ${i} about forces.`,
).join(" ");
const OFFSET = TEXT.indexOf("mass");

function backend() {
  const state = {
    asked: 0,
    enrichmentCalls: 0,
    sim: {} as Record<string, number>,
    rating: null as number | null,
    published: [] as string[],
  };
  const highlight = () => ({
    id: "h-1",
    lecture_id: "lec-m15",
    lecture_version_id: "ver-m15",
    paragraph_ordinal: 0,
    text_range_offset: OFFSET,
    text_range_length: 4,
    highlighted_text: "mass",
    question_id: "q-1",
    concept_tag: "Forces",
    tenant_type: "school",
    created_at: "2026-10-03T12:00:00Z",
    mark: { paragraph_id: "p1", offset: OFFSET, length: 4 },
  });
  const myHighlight = () => ({
    id: "h-1",
    highlighted_text: "mass",
    concept_tag: "Forces",
    created_at: "2026-10-03T12:00:00Z",
    lecture: { id: "lec-m15", title: "Newton's Laws", topic: "Forces" },
    paragraph_ordinal: 0,
    question_id: "q-1",
    flashcard: {
      id: "fc-1",
      front_text: "mass",
      back_text: "Mass is the amount of matter.",
      back_is_placeholder: false,
      status: "active",
      concept_tag: "Forces",
      created_at: "2026-10-03T12:00:01Z",
    },
  });
  const ready = {
    concept_id: "Forces",
    concept_label: "Forces",
    status: "ready",
    real_world_uses: [
      { title: "Rickshaws", description: "Heavier loads need more force." },
      { title: "Cricket", description: "A bat changes the ball's momentum." },
    ],
    careers: [{ id: "c1", name: "Civil Engineer", sector: "Engineering" }],
    mini_sim: {
      title: "Push the cart",
      scenario: "A cart on a road in Lahore.",
      variables: [
        {
          key: "mass",
          label: "Mass",
          unit: "kg",
          min: 1,
          max: 100,
          step: 1,
          default: 10,
        },
        {
          key: "accel",
          label: "Acceleration",
          unit: "m/s²",
          min: 0,
          max: 10,
          step: 1,
          default: 2,
        },
      ],
      output: { label: "Force", unit: "N", expression: "mass * accel" },
    },
    generated_at: "2026-10-03T12:00:00Z",
    refreshing: false,
  };

  async function install(page: Page) {
    await installStudentMocks(page, ({ method, path, body }) => {
      if (method === "POST" && path === "/students/me/lectures/lec-m15/open")
        return viewerPayload(TEXT);
      if (method === "POST" && path.endsWith("/sessions/sess-m15/questions")) {
        state.asked += 1;
        // Server-side dedupe: only the first ask creates a card + publishes.
        if (state.asked === 1)
          state.published.push("student.flashcard.created");
        return {
          id: `q-${state.asked}`,
          student_user_id: "stu-1",
          session_id: "sess-m15",
          lecture_id: "lec-m15",
          tenant_type: "school",
          highlight_text: (body as { highlight_text: string }).highlight_text,
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
        return state.asked > 0 ? [highlight()] : [];
      }
      if (
        method === "GET" &&
        path === "/students/me/lectures/lec-m15/concepts"
      ) {
        return [
          {
            concept_id: "Forces",
            label: "Forces",
            first_paragraph_id: "p1",
            first_paragraph_ordinal: 0,
          },
        ];
      }
      if (
        method === "GET" &&
        path === "/students/me/lectures/lec-m15/enrichment"
      ) {
        state.enrichmentCalls += 1;
        return state.enrichmentCalls === 1
          ? {
              ...ready,
              status: "pending",
              real_world_uses: [],
              careers: [],
              mini_sim: null,
            }
          : ready;
      }
      if (path === "/students/me/lectures/lec-m15/simulation") {
        if (method === "PUT")
          state.sim = (body as { values: Record<string, number> }).values;
        return { concept_id: "Forces", values: state.sim, was_reset: false };
      }
      if (path === "/students/me/lectures/lec-m15/rating") {
        if (method === "PUT")
          state.rating = (body as { rating: number }).rating;
        return {
          lecture_id: "lec-m15",
          rating: method === "PUT" ? state.rating : null,
        };
      }
      return undefined;
    });
    await page.route("**/api/v1/students/me/highlights?*", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          items: state.asked > 0 ? [myHighlight()] : [],
          total: state.asked > 0 ? 1 : 0,
          page: 1,
          page_size: 20,
          pages: 1,
        }),
      }),
    );
  }
  return { state, install };
}

test.describe("M-15 full journey @smoke @mock", () => {
  test("highlight → flashcard → marks → enrichment → mini-sim → My Highlights → rating → RTL", async ({
    page,
    context,
  }) => {
    const api = backend();
    await api.install(page);
    await page.setViewportSize({ width: 1280, height: 700 });

    // 1-4 open, highlight, ask (auto-send), answer arrives
    await page.goto("/student/lectures/lec-m15");
    await expect(page.getByTestId("lecture-paragraph-text")).toBeVisible({
      timeout: 15_000,
    });
    await selectInParagraph(page, "mass");
    await expect.poll(() => api.state.asked, { timeout: 10_000 }).toBe(1);
    // 5-7 flashcard created + event published (once)
    expect(api.state.published).toEqual(["student.flashcard.created"]);
    // 8-9 mark appears and persists on return
    await expect(page.getByTestId("highlight-mark")).toHaveText("mass", {
      timeout: 10_000,
    });
    await page.reload();
    await expect(page.getByTestId("highlight-mark")).toHaveText("mass", {
      timeout: 15_000,
    });

    // 16-20 concept reached → pending (cache miss) → ready
    const card = page.getByTestId("concept-enrichment");
    await expect(card.getByTestId("concept-uses")).toContainText("Rickshaws", {
      timeout: 15_000,
    });
    await expect(card.getByTestId("concept-careers")).toContainText(
      "Civil Engineer",
    );

    // 21-24 mini-sim: change state, saved, restored on return
    await card.getByTestId("mini-sim-slider-mass").fill("30");
    await expect(card.getByTestId("mini-sim-output")).toHaveText("Force: 60 N");
    await expect.poll(() => api.state.sim.mass, { timeout: 5_000 }).toBe(30);
    await page.reload();
    await expect(page.getByTestId("mini-sim-output")).toHaveText(
      "Force: 60 N",
      { timeout: 15_000 },
    );

    // 25-28 completion (scroll to the end) → optional rating → submit 5
    await page.evaluate(() =>
      window.scrollTo(0, document.documentElement.scrollHeight),
    );
    await page.mouse.wheel(0, 4000);
    await expect(page.getByTestId("lecture-rating-prompt")).toBeVisible({
      timeout: 10_000,
    });
    await page.getByRole("radio", { name: "5 stars" }).click();
    await page.getByTestId("lecture-rating-submit").click();
    await expect(page.getByText("Thanks for your rating!")).toBeVisible();
    expect(api.state.rating).toBe(5);

    // 13-15 My Highlights from the nav: highlight + lecture + concept + paired card
    await page
      .getByTestId("student-nav")
      .getByRole("link", { name: "My Highlights" })
      .click();
    const row = page.getByTestId("my-highlight");
    await expect(row.getByTestId("my-highlight-lecture")).toContainText(
      "Newton's Laws",
      { timeout: 15_000 },
    );
    await expect(row.getByTestId("my-highlight-concept")).toContainText(
      "Forces",
    );
    await expect(row.getByTestId("flashcard-front")).toHaveText("mass");

    // 34 RTL/i18n: the same surfaces in Urdu
    await context.addCookies([
      { name: "locale", value: "ur", url: "http://localhost:3100" },
    ]);
    await page.reload();
    await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
    await expect(
      page.getByRole("heading", { name: "میری نمایاں عبارتیں" }),
    ).toBeVisible({ timeout: 15_000 });
  });

  test("re-edited lecture: mark disappears silently, flashcard still listed (§5.5)", async ({
    page,
  }) => {
    await installStudentMocks(page, ({ method, path }) => {
      if (method === "POST" && path === "/students/me/lectures/lec-m15/open") {
        return viewerPayload("Force is a push or a pull acting on an object.");
      }
      if (
        method === "GET" &&
        path === "/students/me/lectures/lec-m15/highlights"
      ) {
        // Server re-verified the anchor against the edited version → mark: null.
        return [
          {
            id: "h-1",
            lecture_id: "lec-m15",
            lecture_version_id: "ver-m15",
            paragraph_ordinal: 0,
            text_range_offset: OFFSET,
            text_range_length: 4,
            highlighted_text: "mass",
            question_id: "q-1",
            concept_tag: "Forces",
            tenant_type: "school",
            created_at: "2026-10-03T12:00:00Z",
            mark: null,
          },
        ];
      }
      return undefined;
    });
    await page.route("**/api/v1/students/me/highlights?*", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          items: [
            {
              id: "h-1",
              highlighted_text: "mass",
              concept_tag: "Forces",
              created_at: "2026-10-03T12:00:00Z",
              lecture: {
                id: "lec-m15",
                title: "Newton's Laws",
                topic: "Forces",
              },
              paragraph_ordinal: 0,
              question_id: "q-1",
              flashcard: {
                id: "fc-1",
                front_text: "mass",
                back_text: "Mass is the amount of matter.",
                back_is_placeholder: false,
                status: "active",
                concept_tag: "Forces",
                created_at: "2026-10-03T12:00:01Z",
              },
            },
          ],
          total: 1,
          page: 1,
          page_size: 20,
          pages: 1,
        }),
      }),
    );
    await page.goto("/student/lectures/lec-m15");
    await expect(page.getByTestId("lecture-paragraph-text")).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByTestId("highlight-mark")).toHaveCount(0);
    await expect(page.getByTestId("lecture-viewer-error")).toHaveCount(0);
    await page.goto("/student/highlights");
    await expect(page.getByTestId("flashcard-front")).toHaveText("mass", {
      timeout: 15_000,
    });
  });
});
