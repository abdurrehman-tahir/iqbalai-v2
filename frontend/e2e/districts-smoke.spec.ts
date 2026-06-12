/**
 * T-029 — Districts admin smoke test (E2E, @smoke).
 *
 * Self-contained: API is mocked via installPlatformAdminMocks (no live backend),
 * and the session is seeded directly into sessionStorage so we skip the OIDC
 * round-trip. Exercises the create flow and asserts the new district renders.
 *
 * Run:
 *   pnpm exec playwright test e2e/districts-smoke.spec.ts
 */

import { test, expect, type Page } from "@playwright/test";
import { installPlatformAdminMocks } from "./helpers/mock-api";

const BASE_URL = process.env.E2E_BASE_URL ?? "http://localhost:3000";

async function seedSession(page: Page) {
  await page.addInitScript(() => {
    sessionStorage.setItem("iqbalai_access_token", "e2e-test-access-token");
    sessionStorage.setItem(
      "iqbalai_user",
      JSON.stringify({
        user_id: "user-platform-admin-1",
        email: "admin@iqbalai.test",
        role: "platform_admin",
        tos_acceptance_required: false,
        current_tos_version_id: null,
      }),
    );
  });
}

test.describe("Districts admin @smoke", () => {
  test("Platform Admin creates a district and sees it listed", async ({ page }) => {
    await installPlatformAdminMocks(page);
    await seedSession(page);

    await page.goto(`${BASE_URL}/admin/districts`);

    // Empty state first, then create.
    await page.getByRole("button", { name: /add district/i }).click();
    await page.fill("#district-name", "Lahore District");
    await page.fill("#district-region", "Punjab");
    await page.getByRole("button", { name: /^create$/i }).click();

    await expect(page.getByRole("cell", { name: "Lahore District" })).toBeVisible({
      timeout: 5_000,
    });
  });
});
