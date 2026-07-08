/**
 * T-232 — ToS render / scroll / accept / decline smoke (E2E, @smoke).
 */
import { test, expect } from "@playwright/test";
import { installPlatformAdminMocks } from "./helpers/mock-api";

const LONG_TOS = Array.from({ length: 80 }, (_, i) => `Section ${i + 1}: terms line.`).join(
  "\n",
);

test.describe("ToS flows (T-232) @smoke @mock", () => {
  test("bootstrap ToS modal shows text, scrolls, and accepts @smoke", async ({ page }) => {
    const state = await installPlatformAdminMocks(page);
    state.tosContent = LONG_TOS;
    state.tosAccepted = false;

    await page.goto("/login");
    await page.getByLabel(/email/i).fill("admin@iqbalai.test");
    await page.getByLabel(/^password$/i).fill("devpassword");
    await page.getByRole("button", { name: /sign in/i }).click();

    const dialog = page.getByRole("dialog", { name: /terms of service/i });
    await expect(dialog).toBeVisible({ timeout: 10_000 });

    const content = page.getByLabel("Terms of Service content");
    await expect(content).toContainText("Section 1:");

    const acceptBtn = page.getByRole("button", { name: /accept/i });
    await expect(acceptBtn).toBeDisabled();

    await content.evaluate((el: HTMLElement) => el.scrollTo(0, el.scrollHeight));
    await expect(acceptBtn).toBeEnabled({ timeout: 3_000 });
    await acceptBtn.click();

    await page.waitForURL("**/admin**", { timeout: 10_000 });
  });

  test("decline ToS shows suspended state @smoke", async ({ page }) => {
    const state = await installPlatformAdminMocks(page);
    state.tosAccepted = false;

    await page.route("**/api/v1/users/me/decline-tos", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ data: { declined: true, status: "suspended" }, message: "ok" }),
      });
    });

    await page.goto("/login");
    await page.getByLabel(/email/i).fill("admin@iqbalai.test");
    await page.getByLabel(/^password$/i).fill("devpassword");
    await page.getByRole("button", { name: /sign in/i }).click();

    await expect(page.getByRole("dialog")).toBeVisible({ timeout: 10_000 });
    await page.getByRole("button", { name: /decline/i }).click();

    await expect(page.getByRole("heading", { name: /account suspended/i })).toBeVisible({
      timeout: 5_000,
    });
  });
});
