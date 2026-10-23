/**
 * M-16 next-day review — teacher acceptance paths (@smoke @mock).
 * Reviews are reached from the teacher nav; the card renders the locked
 * Flow 7 §3.3 layout. Backend answered by e2e/helpers/m16-mocks.ts.
 */
import { expect, test } from "@playwright/test";
import { REVIEW_SUMMARY, installReviewMocks } from "./helpers/m16-mocks";

test.describe("M-16 next-day review @smoke @mock", () => {
  test("teacher reaches Daily reviews from the nav and opens a card (T-201)", async ({
    page,
  }) => {
    await installReviewMocks(page);
    await page.goto("/teacher");
    await page.getByRole("link", { name: "Daily reviews" }).click();
    await expect(page.getByRole("heading", { name: "Daily reviews" })).toBeVisible({
      timeout: 15_000,
    });

    await page.getByRole("link", { name: /Grade 9 Physics/ }).click();
    const card = page.getByTestId("review-card");
    await expect(card).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId("review-summary")).toContainText(
      "Students mixed up which body each force acts on.",
    );
    await expect(page.getByTestId("review-critical")).toContainText(
      "Why do action and reaction forces not cancel (a)?",
    );
    await expect(page.getByTestId("review-frequent")).toContainText("(b)");
    await expect(page.getByTestId("review-mini")).toContainText("Force pairs always act");
  });

  test("deep link renders the card directly (T-201)", async ({ page }) => {
    await installReviewMocks(page);
    await page.goto("/teacher/reviews/rev-1");
    await expect(page.getByTestId("review-card")).toBeVisible({ timeout: 15_000 });
  });

  test("teacher answers the reflective question by text (T-202)", async ({ page }) => {
    const recorded = await installReviewMocks(page);
    await page.goto("/teacher/reviews/rev-1");
    const reflection = page.getByTestId("review-reflection");
    await expect(reflection).toContainText("worked example with everyday objects", {
      timeout: 15_000,
    });
    await reflection.getByRole("textbox").fill("I'll bring two spring scales tomorrow.");
    await reflection.getByRole("textbox").press("Enter");
    await expect(reflection.getByRole("status")).toBeVisible();
    expect(recorded).toContainEqual({
      method: "POST",
      path: "/reviews/rev-1/reflection",
      body: { response: "I'll bring two spring scales tomorrow." },
    });
  });

  test("drill-down shows names, replies to a student and skips (T-203)", async ({ page }) => {
    const recorded = await installReviewMocks(page);
    await page.goto("/teacher/reviews/rev-1");
    const critical = page.getByTestId("review-critical");
    await critical.getByRole("button", { name: "View details" }).click({ timeout: 15_000 });

    const modal = page.getByTestId("cluster-drilldown");
    await expect(modal).toContainText("Ali Raza");
    await expect(modal).toContainText("Why don't the forces cancel? (a)");

    await modal.getByRole("button", { name: "Reply" }).first().click();
    await modal.getByRole("textbox").fill("Look at the free-body diagram on page 12.");
    await modal.getByRole("textbox").press("Enter");
    await expect
      .poll(() => recorded.some((r) => r.path === "/reviews/rev-1/replies"))
      .toBe(true);
    expect(recorded.find((r) => r.path === "/reviews/rev-1/replies")?.body).toEqual({
      cluster_ref: "a",
      student_user_id: "stu-0",
      body: "Look at the free-body diagram on page 12.",
    });

    await modal.getByRole("button", { name: "Skip this cluster" }).click();
    await expect
      .poll(() => recorded.find((r) => r.path === "/reviews/rev-1/skips")?.body)
      .toEqual({ cluster_ref: "a" });
  });

  test("publish, dismiss/reopen and Edit Main Lecture actions (T-205)", async ({ page }) => {
    const recorded = await installReviewMocks(page);
    await page.goto("/teacher/reviews/rev-1");
    const actions = page.getByTestId("review-actions");
    await expect(actions).toBeVisible({ timeout: 15_000 });
    await expect(actions.getByRole("button", { name: "Schedule Group Study" })).toBeDisabled();

    await actions.getByRole("button", { name: "Publish Mini-Lecture" }).click();
    await expect(actions.getByRole("button", { name: "Mini-lecture published" })).toBeDisabled();

    await actions.getByRole("button", { name: "Dismiss without action" }).click();
    await actions.getByRole("button", { name: "Reopen review" }).click();
    await expect(actions.getByRole("button", { name: "Dismiss without action" })).toBeVisible();

    await actions.getByRole("button", { name: "Edit Main Lecture" }).click();
    await expect(page).toHaveURL(/\/teacher\/lectures\/lec-1\?from_review=rev-1/);
    await expect(page.getByTestId("from-review-banner")).toBeVisible({ timeout: 15_000 });

    // Only the review writes — the editor's own edit-session calls are out of scope here.
    expect(recorded.map((r) => r.path).filter((p) => p.startsWith("/reviews/"))).toEqual([
      "/reviews/rev-1/publish-mini",
      "/reviews/rev-1/dismiss",
      "/reviews/rev-1/reopen",
      "/reviews/rev-1/edit-main",
    ]);
  });

  test("lecture Reviews tab lists the lecture's review history (T-206)", async ({ page }) => {
    await installReviewMocks(page, ({ method, path }) =>
      method === "GET" && path === "/reviews" ? [REVIEW_SUMMARY] : undefined,
    );
    await page.goto("/teacher/lectures/lec-1?tab=reviews");
    await expect(page.getByRole("tab", { name: "Reviews" })).toHaveAttribute(
      "aria-selected",
      "true",
      { timeout: 15_000 },
    );
    await expect(page.getByTestId("reviews-list")).toContainText("Grade 9 Physics");
  });
});
