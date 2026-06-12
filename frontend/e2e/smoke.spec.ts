import { expect, test } from "@playwright/test";

/**
 * T-223 — Trivial harness smoke test.
 *
 * Proves the Playwright harness is non-vacuous: it boots the Next.js dev server
 * (see playwright.config.ts `webServer`) and loads a real page. Tagged @smoke so
 * `pnpm e2e --grep @smoke` (the PR-time CI job) picks it up; the full suite runs
 * nightly. Richer acceptance-path smokes land in T-231/T-232/T-235.
 */
test("login page renders @smoke", async ({ page }) => {
  const response = await page.goto("/login");
  expect(response?.status() ?? 200).toBeLessThan(400);
  await expect(page.locator("body")).toBeVisible();
});
