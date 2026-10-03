/**
 * T-188 — My Highlights acceptance path (@smoke @mock): nav → page with real
 * content → flashcard flip → "Open in lecture" lands on the yellow mark.
 */
import { expect, test } from "@playwright/test";
import { installStudentMocks, PARA_TEXT } from "./helpers/m15-mocks";

const OFFSET = PARA_TEXT.indexOf("mass");

const myHighlight = {
  id: "h-1",
  highlighted_text: "mass",
  concept_tag: "forces/newton-2",
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
    concept_tag: "forces/newton-2",
    created_at: "2026-10-03T12:00:01Z",
  },
};

test.describe("M-15 My Highlights @smoke @mock", () => {
  test("reachable from nav, shows highlight + flashcard, links back to the mark", async ({
    page,
  }) => {
    await installStudentMocks(page, ({ method, path }) => {
      if (method === "GET" && path === "/students/me/highlights") {
        return undefined; // answered below (paginated envelope is top-level)
      }
      if (
        method === "GET" &&
        path === "/students/me/lectures/lec-m15/highlights"
      ) {
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
            concept_tag: "forces/newton-2",
            tenant_type: "school",
            created_at: "2026-10-03T12:00:00Z",
            mark: { paragraph_id: "p1", offset: OFFSET, length: 4 },
          },
        ];
      }
      return undefined;
    });
    // PaginatedEnvelope is returned top-level (not wrapped in `data`).
    await page.route("**/api/v1/students/me/highlights?*", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          items: [myHighlight],
          total: 1,
          page: 1,
          page_size: 20,
          pages: 1,
        }),
      }),
    );

    await page.goto("/student");
    const nav = page.getByTestId("student-nav");
    await expect(nav).toBeVisible({ timeout: 15_000 });
    await nav.getByRole("link", { name: "My Highlights" }).click();

    await expect(page).toHaveURL(/\/student\/highlights$/);
    await expect(
      page.getByRole("heading", { name: "My Highlights" }),
    ).toBeVisible();
    const row = page.getByTestId("my-highlight");
    await expect(row).toHaveCount(1);
    await expect(row.getByTestId("my-highlight-lecture")).toContainText(
      "Newton's Laws",
    );
    await expect(row.getByTestId("my-highlight-concept")).toContainText(
      "forces/newton-2",
    );
    await expect(row.getByTestId("flashcard-front")).toHaveText("mass");

    await row.getByTestId("flashcard-flip").click();
    await expect(row.getByTestId("flashcard-back")).toHaveText(
      "Mass is the amount of matter.",
    );

    await row.getByTestId("my-highlight-open").click();
    await expect(page).toHaveURL(
      /\/student\/lectures\/lec-m15\?highlight=h-1$/,
    );
    const mark = page.locator(
      '[data-testid="highlight-mark"][data-highlight-id="h-1"]',
    );
    await expect(mark).toBeVisible({ timeout: 15_000 });
    await expect(mark).toBeFocused();
  });

  test("works at 360px wide without horizontal scrolling", async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 740 });
    await installStudentMocks(page);
    await page.route("**/api/v1/students/me/highlights?*", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          items: [myHighlight],
          total: 1,
          page: 1,
          page_size: 20,
          pages: 1,
        }),
      }),
    );
    await page.goto("/student/highlights");
    await expect(page.getByTestId("my-highlight")).toBeVisible({
      timeout: 15_000,
    });
    const overflow = await page.evaluate(
      () =>
        document.documentElement.scrollWidth >
        document.documentElement.clientWidth,
    );
    expect(overflow).toBe(false);
  });
});
