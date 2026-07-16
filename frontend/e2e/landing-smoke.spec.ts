/**
 * QA E03/E05 — landing entry point smoke (@smoke).
 *
 * The landing page's "Get Started" CTA was a bare <button> with no handler and no href,
 * so the only way into the product was typing /login by hand. This proves the public
 * entry path works: land on /, click the CTA, arrive at the login page.
 *
 * No auth required — both pages are public.
 */
import { test, expect } from "@playwright/test";

test("@smoke landing CTA takes a visitor to the login page", async ({ page }) => {
  await page.goto("/");

  const cta = page.getByRole("link", { name: /get started/i });
  await expect(cta).toBeVisible();

  await cta.click();

  await expect(page).toHaveURL(/\/login$/);
});
