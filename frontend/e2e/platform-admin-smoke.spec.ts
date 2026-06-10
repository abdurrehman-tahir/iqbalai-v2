/**
 * T-026 — Platform Admin smoke test (E2E @smoke @mock).
 *
 * Full M-01 acceptance flow with route mocks (no Authentik / compose required on PR).
 * Real Authentik + compose bring-up is a manual / nightly concern; API contract
 * coverage lives in admin-create-real.spec.ts (@smoke @real).
 */
import { test, expect, type Page } from "@playwright/test";
import { installPlatformAdminMocks } from "./helpers/mock-api";

async function bootstrapAdmin(page: Page) {
  const state = await installPlatformAdminMocks(page);
  state.tosAccepted = false;
  await page.goto("/auth/callback?code=e2e-test-code");
  return state;
}

async function acceptTos(page: Page) {
  await expect(
    page.getByRole("dialog", { name: /terms of service/i }),
  ).toBeVisible({ timeout: 10_000 });
  const content = page.locator('[aria-label="Terms of Service content"]');
  await content.evaluate((el: HTMLElement) => el.scrollTo(0, el.scrollHeight));
  await expect(page.getByRole("button", { name: /i accept/i })).toBeEnabled({
    timeout: 3_000,
  });
  await page.getByRole("button", { name: /i accept/i }).click();
  await page.waitForURL("**/admin**", { timeout: 10_000 });
}

test.describe("Platform Admin smoke test (M-01 acceptance criteria) @smoke @mock", () => {
  test.setTimeout(120_000);

  test("Full Platform Admin onboarding flow @smoke", async ({ page }) => {
    const state = await bootstrapAdmin(page);
    await acceptTos(page);

    await expect(page).toHaveURL(/\/admin/);

    await page.click('a:has-text("Languages")');
    for (const code of ["en", "ur", "sd", "ps"]) {
      await expect(page.locator(`p[lang="${code}"]`)).toBeVisible();
    }

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
      await expect(page.getByRole("cell", { name, exact: true })).toBeVisible({
        timeout: 5_000,
      });
    }

    await page.click('a:has-text("Teaching Personas")');
    await expect(page.getByRole("button", { name: /edit prompt/i })).toHaveCount(
      5,
      { timeout: 5_000 },
    );
    await page.getByRole("button", { name: /edit prompt/i }).first().click();
    await page.fill("#system_prompt_en", "You are a strict, focused tutor.");
    await page.getByRole("button", { name: /save changes/i }).click();
    await expect(page.getByRole("dialog")).not.toBeVisible({ timeout: 3_000 });

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

    await page.getByRole("link", { name: "ToS & Disclaimer" }).click();
    await page
      .getByRole("main")
      .getByRole("button", { name: /publish new version/i })
      .first()
      .click();
    await page.fill(
      "#tos-content",
      "These are the Terms of Service for IqbalAI. By using this platform you agree to our terms.",
    );
    await page.getByRole("button", { name: /^publish$/i }).click();
    await expect(page.getByRole("dialog")).not.toBeVisible({ timeout: 5_000 });
    await expect(page.getByText("Version 1")).toBeVisible({ timeout: 5_000 });

    await page.goto("/admin/tos?tab=disclaimer");
    await page
      .getByRole("main")
      .getByRole("button", { name: /publish new version/i })
      .first()
      .click();
    await page.fill(
      "#tos-content",
      "AI outputs may contain errors. Verify with authoritative sources.",
    );
    await page.getByRole("button", { name: /^publish$/i }).click();
    await expect(page.getByRole("dialog")).not.toBeVisible({ timeout: 5_000 });
    await expect(page.getByText("Version 1")).toBeVisible({ timeout: 5_000 });

    await page.getByRole("link", { name: "Audit Log" }).click();
    await page.waitForURL("**/admin/audit-log**");
    await expect(page.getByRole("heading", { name: "Audit Log", level: 1 })).toBeVisible();
    expect(state.auditLog.some((e) => e.action === "exam_syllabus.created")).toBe(true);
    expect(state.auditLog.some((e) => e.action === "tos.published")).toBe(true);
  });

  test("ToS decline → logs user out @smoke", async ({ page }) => {
    await bootstrapAdmin(page);
    await expect(
      page.getByRole("dialog", { name: /terms of service/i }),
    ).toBeVisible({ timeout: 10_000 });
    await page.getByRole("button", { name: /decline/i }).click();
    await expect(page.getByRole("heading", { name: /account suspended/i })).toBeVisible({
      timeout: 10_000,
    });
  });
});
