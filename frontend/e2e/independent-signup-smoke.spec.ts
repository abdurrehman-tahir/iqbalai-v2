/**
 * T-069 — Independent signup smoke test (@smoke).
 */

import { test, expect, type Page, type Route } from "@playwright/test";

const BASE_URL = process.env.E2E_BASE_URL ?? "http://localhost:3000";

function envelope<T>(data: T) {
  return JSON.stringify({ data, message: "ok" });
}

async function installIndependentSignupMocks(page: Page) {
  await page.route(
    (url) => url.pathname.includes("/api/v1/independent/signup"),
    async (route: Route) => {
      const method = route.request().method();
      if (method === "GET") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: envelope({
            roles: ["independent_teacher", "independent_student"],
            languages: ["en", "ur", "sd", "ps"],
          }),
        });
        return;
      }
      if (method === "POST") {
        await route.fulfill({
          status: 201,
          contentType: "application/json",
          body: envelope({
            user_id: "ind-user-1",
            email: "teacher@example.com",
            role: "independent_teacher",
            tenant_type: "independent",
            message: "Account created",
          }),
        });
        return;
      }
      await route.continue();
    },
  );
}

test.describe("@smoke independent signup", () => {
  test("signup form renders and submits", async ({ page }) => {
    await installIndependentSignupMocks(page);
    await page.goto(`${BASE_URL}/independent/signup`);

    await expect(page.getByRole("heading", { name: /Create your independent account/i })).toBeVisible();
    await page.getByLabel(/Full name/i).fill("Indie Teacher");
    await page.getByLabel(/^Email$/i).fill("teacher@example.com");
    await page.getByLabel(/^Password$/i).fill("securepass1");
    await page.getByLabel(/Confirm password/i).fill("securepass1");
    await page.getByRole("button", { name: /Create account/i }).click();

    await expect(page.getByText(/Your account is ready/i)).toBeVisible();
  });
});
