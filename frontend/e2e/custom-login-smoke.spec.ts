/**
 * M-07b T-246 — Custom login smoke (@smoke @mock).
 *
 * Validates the BFF login surface: branded form, signup hub, forgot-password,
 * cookie session (no sessionStorage JWT), and no Authentik UI navigation.
 */

import { test, expect } from "@playwright/test";
import {
  blockAuthentikUi,
  installBffLoginMocks,
  loginViaForm,
  DEFAULT_ADMIN,
  DEFAULT_TEACHER,
  envelope,
  API_BASE,
} from "./helpers/bff-auth";

test.describe("Custom login smoke (M-07b) @smoke @mock", () => {
  test.beforeEach(async ({ page }) => {
    await blockAuthentikUi(page);
  });

  test("login page shows email + password form, not Authentik redirect", async ({
    page,
  }) => {
    await page.goto("/login");
    await expect(page.getByLabel(/email/i)).toBeVisible();
    await expect(page.getByLabel(/^password$/i)).toBeVisible();
    await expect(page.getByRole("button", { name: /sign in/i })).toBeVisible();
    await expect(page.getByRole("link", { name: /forgot password/i })).toBeVisible();
    await expect(page.getByRole("link", { name: /create account/i })).toHaveAttribute(
      "href",
      "/signup",
    );
    await expect(page.getByRole("button", { name: /sign in with authentik/i })).toHaveCount(
      0,
    );
  });

  test("Platform Admin — custom login → /admin @smoke", async ({ page }) => {
    await installBffLoginMocks(page, DEFAULT_ADMIN);
    await loginViaForm(page, "admin@iqbalai.dev", "devpassword");
    await page.waitForURL("**/admin**", { timeout: 10_000 });

    const token = await page.evaluate(() =>
      sessionStorage.getItem("iqbalai_access_token"),
    );
    expect(token).toBeNull();
  });

  test("School Teacher — custom login → /teacher @smoke", async ({ page }) => {
    await installBffLoginMocks(page, DEFAULT_TEACHER);
    await loginViaForm(page, "teacher@iqbalai.dev", "devpassword");
    await page.waitForURL("**/teacher**", { timeout: 10_000 });
  });

  test("signup hub renders four paths @smoke", async ({ page }) => {
    await page.goto("/signup");
    await expect(page.getByText(/school invite/i)).toBeVisible();
    await expect(page.getByText(/independent teacher or student/i)).toBeVisible();
    await expect(page.getByText(/^parent$/i)).toBeVisible();
    await expect(page.getByText(/school staff or student/i)).toBeVisible();
    await expect(page.getByRole("link", { name: /accept invite/i })).toHaveAttribute(
      "href",
      "/accept-invite",
    );
  });

  test("independent signup success lands on custom /login @smoke", async ({ page }) => {
    await page.route(`${API_BASE}/independent/signup**`, async (route) => {
      const method = route.request().method();
      if (method === "GET") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: envelope({
            roles: ["independent_teacher", "independent_student"],
            languages: ["en"],
          }),
        });
        return;
      }
      if (method === "POST") {
        await route.fulfill({
          status: 201,
          contentType: "application/json",
          body: envelope({
            user_id: "ind-1",
            email: "indie@example.com",
            role: "independent_teacher",
            tenant_type: "independent",
            message: "ok",
          }),
        });
        return;
      }
      await route.continue();
    });

    await page.route(`${API_BASE}/independent/students/me/exam-frameworks**`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: envelope([]),
      });
    });

    await page.goto("/independent/signup");
    await page.getByLabel(/full name/i).fill("Indie User");
    await page.getByLabel(/^email$/i).fill("indie@example.com");
    await page.getByLabel(/^password$/i).fill("securepass1");
    await page.getByLabel(/confirm password/i).fill("securepass1");
    await page.getByRole("button", { name: /create account/i }).click();

    await expect(page.getByText(/account is ready/i)).toBeVisible();
    await page.getByRole("button", { name: /sign in/i }).click();
    await page.waitForURL("**/login?email=indie**");
    expect(page.url()).not.toContain("9000");
  });

  test("parent signup success lands on custom /login @smoke", async ({ page }) => {
    await page.route(`${API_BASE}/parents/signup**`, async (route) => {
      const method = route.request().method();
      if (method === "GET") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: envelope({ languages: ["en"] }),
        });
        return;
      }
      if (method === "POST") {
        await route.fulfill({
          status: 201,
          contentType: "application/json",
          body: envelope({
            user_id: "parent-1",
            email: "parent@example.com",
            role: "parent",
            message: "ok",
          }),
        });
        return;
      }
      await route.continue();
    });

    await page.goto("/parent/signup");
    await page.getByLabel(/full name/i).fill("Parent User");
    await page.getByLabel(/^email$/i).fill("parent@example.com");
    await page.getByLabel(/^password$/i).fill("securepass1");
    await page.getByLabel(/confirm password/i).fill("securepass1");
    await page.getByRole("button", { name: /create account/i }).click();

    await expect(page.getByText(/account is ready/i)).toBeVisible();
    await page.getByRole("button", { name: /sign in/i }).click();
    await page.waitForURL("**/login?email=parent**");
  });

  test("forgot-password shows success without enumeration @smoke", async ({ page }) => {
    await page.route(`${API_BASE}/auth/forgot-password`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: envelope(null),
      });
    });

    await page.goto("/login/forgot-password");
    await page.getByLabel(/email/i).fill("ghost@iqbalai.dev");
    await page.getByRole("button", { name: /send reset link/i }).click();
    await expect(
      page.getByText(/if an account exists/i),
    ).toBeVisible({ timeout: 5_000 });
  });
});
