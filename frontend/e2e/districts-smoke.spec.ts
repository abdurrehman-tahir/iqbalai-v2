/**
 * T-029 — Districts admin smoke test (E2E, @smoke).
 *
 * Self-contained: API is mocked via installPlatformAdminMocks (no live backend).
 * Since T-245 the session is an HttpOnly cookie and the shell reads "who am I"
 * from GET /auth/me — which the mock answers — so no sessionStorage seeding is
 * needed (T-247). Exercises the create flow and asserts the new district renders.
 *
 * Run:
 *   pnpm exec playwright test e2e/districts-smoke.spec.ts
 */

import { test, expect } from "@playwright/test";
import { installPlatformAdminMocks } from "./helpers/mock-api";

const BASE_URL = process.env.E2E_BASE_URL ?? "http://localhost:3000";

test.describe("Districts admin @smoke", () => {
  test("Platform Admin creates a district and sees it listed", async ({ page }) => {
    await installPlatformAdminMocks(page);

    await page.goto(`${BASE_URL}/admin/districts`);

    // Empty state first, then create.
    await page.getByRole("button", { name: /add district/i }).click();
    await page.fill("#district-name", "Lahore District");
    await page.fill("#district-region", "Punjab");
    await page.getByRole("button", { name: /^create$/i }).click();

    await expect(
      page.getByRole("cell", { name: "Lahore District", exact: true }),
    ).toBeVisible({
      timeout: 5_000,
    });
  });
});
