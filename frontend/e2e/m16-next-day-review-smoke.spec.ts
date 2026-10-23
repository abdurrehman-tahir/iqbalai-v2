/**
 * M-16 next-day review — teacher acceptance paths (@smoke @mock).
 * Reviews are reached from the teacher nav; the card renders the locked
 * Flow 7 §3.3 layout. Backend answered by e2e/helpers/m16-mocks.ts.
 */
import { expect, test } from "@playwright/test";
import { installReviewMocks } from "./helpers/m16-mocks";

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
});
