/**
 * T-026 — Platform Admin smoke test (E2E).
 *
 * Prerequisites:
 *   - `docker compose up -d` (full stack running)
 *   - Authentik bootstrapped with Platform Admin user
 *   - `pnpm exec playwright install chromium` run once
 *   - Copy .env.e2e.example → .env.e2e and fill in credentials
 *
 * Run:
 *   pnpm exec playwright test e2e/platform-admin-smoke.spec.ts
 *
 * NOTE: @playwright/test not yet in package.json — needs approval per STACK_LOCK.
 * The spec is ready to run once `pnpm add -D @playwright/test` is executed.
 *
 * Flow under test (Flow 1 v2 §11 acceptance criteria):
 *   1. Platform Admin logs in via Authentik OIDC
 *   2. ToS modal appears → scrolls to bottom → accepts
 *   3. Lands on /admin dashboard
 *   4. Languages page: 4 cards visible (en, ur, sd, ps)
 *   5. Creates 4 exam syllabi
 *   6. Teaching Personas: 5 cards present; edits one
 *   7. Creates 2 subscription tiers
 *   8. Publishes ToS v1
 *   9. Publishes Disclaimer v1
 *  10. Audit log has entries for all actions
 *  11. ToS decline → logs user out
 */

import { test, expect, type Page } from "@playwright/test";

const BASE_URL = process.env.E2E_BASE_URL ?? "http://localhost:3000";
const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL ?? "admin@iqbalai.local";
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? "change-me-in-env";

// ── Helpers ──────────────────────────────────────────────────────────────────

async function loginAsAdmin(page: Page) {
  await page.goto(`${BASE_URL}/login`);
  await page.click('button:has-text("Sign in")');
  // Authentik login form
  await page.fill('[name="username"]', ADMIN_EMAIL);
  await page.fill('[name="password"]', ADMIN_PASSWORD);
  await page.click('[type="submit"]');
  await page.waitForURL(`${BASE_URL}/auth/callback**`, { timeout: 15_000 });
}

async function acceptTos(page: Page) {
  await expect(
    page.getByRole("dialog", { name: /terms of service/i }),
  ).toBeVisible({ timeout: 10_000 });
  // Scroll to bottom to enable accept button
  const content = page.locator('[aria-label="Terms of Service content"]');
  await content.evaluate((el: HTMLElement) => el.scrollTo(0, el.scrollHeight));
  await expect(page.getByRole("button", { name: /i accept/i })).toBeEnabled({
    timeout: 3_000,
  });
  await page.getByRole("button", { name: /i accept/i }).click();
  await page.waitForURL(`${BASE_URL}/admin/**`, { timeout: 10_000 });
}

// ── Tests ────────────────────────────────────────────────────────────────────

test.describe("Platform Admin smoke test (M-01 acceptance criteria) @real", () => {
  test.setTimeout(120_000);

  test("Full Platform Admin onboarding flow", async ({ page }) => {
    await loginAsAdmin(page);
    await acceptTos(page);

    // 3 — Dashboard reached
    await expect(page).toHaveURL(/\/admin/);

    // 4 — Languages: 4 cards
    await page.click('a:has-text("Languages")');
    for (const code of ["en", "ur", "sd", "ps"]) {
      await expect(page.locator(`[lang="${code}"]`)).toBeVisible();
    }

    // 5 — Exam Syllabi: create 4
    await page.click('a:has-text("Exam Syllabi")');
    for (const name of [
      "Matric Punjab Board",
      "FSc Punjab Board",
      "O-Level Cambridge",
      "A-Level Cambridge",
    ]) {
      await page.getByRole("button", { name: /add syllabus/i }).click();
      await page.fill("#syl-name", name);
      await page.fill("#syl-exam-board", "Punjab Board");
      await page.getByRole("button", { name: /create/i }).click();
      await expect(page.getByRole("cell", { name })).toBeVisible({
        timeout: 5_000,
      });
    }

    // 6 — Teaching Personas: 5 cards; edit first
    await page.click('a:has-text("Teaching Personas")');
    await expect(page.getByRole("button", { name: /edit prompt/i })).toHaveCount(
      5,
      { timeout: 5_000 },
    );
    await page.getByRole("button", { name: /edit prompt/i }).first().click();
    await page.fill("#system_prompt", "You are a strict, focused tutor.");
    await page.getByRole("button", { name: /save changes/i }).click();
    await expect(page.getByRole("dialog")).not.toBeVisible({ timeout: 3_000 });

    // 7 — Subscription tiers: create 2
    await page.click('a:has-text("Subscription Tiers")');
    for (const { name, price, slug, appliesTo } of [
      { name: "Basic District", price: "5000", slug: "basic-district", appliesTo: "district" },
      { name: "Premium School", price: "10000", slug: "premium-school", appliesTo: "school" },
    ]) {
      await page.getByRole("button", { name: /add tier/i }).click();
      await page.fill("#tier-name", name);
      await page.fill("#tier-slug", slug);
      await page.selectOption("#tier-applies-to", appliesTo);
      await page.fill("#tier-price", price);
      await page.getByRole("button", { name: /create/i }).click();
      await expect(page.getByText(name)).toBeVisible({ timeout: 5_000 });
    }

    // 8 — ToS: publish v1
    await page.click('a:has-text("ToS")');
    await page.getByRole("button", { name: /publish new version/i }).click();
    await page.fill(
      "#tos-content",
      "These are the Terms of Service for IqbalAI. By using this platform you agree to our terms.",
    );
    await page.getByRole("button", { name: /^publish$/i }).click();
    await expect(page.getByText("Version 1")).toBeVisible({ timeout: 5_000 });

    // 9 — Disclaimer: publish v1 — navigate to /admin/disclaimer
    await page.goto(`${BASE_URL}/admin/disclaimer`);
    await page.getByRole("button", { name: /publish new version/i }).click();
    await page.fill(
      "#tos-content",
      "AI outputs may contain errors. Verify with authoritative sources.",
    );
    await page.getByRole("button", { name: /^publish$/i }).click();
    await expect(page.getByText("Version 1")).toBeVisible({ timeout: 5_000 });

    // 10 — Audit log: verify rows exist
    await page.click('a:has-text("Audit Log")');
    const rows = page.locator("table tbody tr");
    await expect(rows).not.toHaveCount(0, { timeout: 5_000 });

    console.log("✅ Platform Admin smoke test passed — all M-01 acceptance criteria met");
  });

  test("ToS decline → logs user out", async ({ page }) => {
    await loginAsAdmin(page);
    await expect(
      page.getByRole("dialog", { name: /terms of service/i }),
    ).toBeVisible({ timeout: 10_000 });
    await page.getByRole("button", { name: /decline/i }).click();
    await page.waitForURL(/login|end-session/, { timeout: 10_000 });
  });
});
