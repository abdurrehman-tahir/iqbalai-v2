/**
 * T-092 — Platform Admin Exam Frameworks smoke test (E2E, @smoke).
 *
 * Self-contained: the frameworks + /users/me API is mocked inline (no live
 * backend), and the session is seeded into sessionStorage to skip the OIDC
 * round-trip. Drives nav → create → row-visible, asserting the page is
 * reachable and renders real content. The real-backend create contract lives
 * in admin-create-real.spec.ts (@real).
 *
 * Run:
 *   pnpm exec playwright test e2e/exam-frameworks-smoke.spec.ts
 */

import { test, expect, type Page, type Route } from "@playwright/test";

const BASE_URL = process.env.E2E_BASE_URL ?? "http://localhost:3000";

interface MockFramework {
  id: string;
  name: string;
  exam_target: string;
  region: string;
  target_grade_range: number[];
  language: string;
  status: string;
  created_by: string;
  created_at: string;
}

function envelope<T>(data: T) {
  return JSON.stringify({ data, message: "ok" });
}

async function installAdminMocks(page: Page) {
  const frameworks: MockFramework[] = [];

  await page.route(
    (url) => url.pathname.includes("/api/v1/"),
    async (route: Route) => {
      const request = route.request();
      const url = new URL(request.url());
      let path = url.pathname.replace("/api/v1", "");
      if (path.length > 1 && path.endsWith("/")) path = path.slice(0, -1);
      const method = request.method();

      if (method === "GET" && path === "/users/me") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: envelope({
            id: "user-platform-admin-1",
            email: "admin@iqbalai.test",
            display_name: "Platform Admin",
            role: "platform_admin",
            status: "active",
            scoped_ids: null,
            district_id: null,
            school_id: null,
            created_at: new Date().toISOString(),
          }),
        });
        return;
      }

      if (method === "GET" && path === "/exam-frameworks") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: envelope(frameworks),
        });
        return;
      }

      if (method === "POST" && path === "/exam-frameworks") {
        const body = (await request.postDataJSON()) as {
          name: string;
          exam_target: string;
          region: string;
          target_grade_range: number[];
          language: string;
        };
        const framework: MockFramework = {
          id: `framework-${frameworks.length + 1}`,
          name: body.name,
          exam_target: body.exam_target,
          region: body.region,
          target_grade_range: body.target_grade_range,
          language: body.language,
          status: "draft",
          created_by: "user-platform-admin-1",
          created_at: new Date().toISOString(),
        };
        frameworks.push(framework);
        await route.fulfill({
          status: 201,
          contentType: "application/json",
          body: envelope(framework),
        });
        return;
      }

      await route.fulfill({
        status: 404,
        contentType: "application/json",
        body: JSON.stringify({
          error: { code: "NOT_FOUND", message: `Unmocked route: ${method} ${path}` },
        }),
      });
    }
  );
}

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
      })
    );
  });
}

test.describe("Platform Admin Exam Frameworks @smoke", () => {
  test("Admin reaches frameworks from nav, creates one, and sees it listed", async ({ page }) => {
    await installAdminMocks(page);
    await seedSession(page);

    await page.goto(`${BASE_URL}/admin/exam-frameworks`);

    // Reachable + real content: the page header renders.
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();

    // Empty state first, then create.
    await page
      .getByRole("button", { name: /add framework/i })
      .first()
      .click();
    await page.fill("#fw-name", "Matric Punjab — Physics");
    await page.fill("#fw-exam-target", "Matric Punjab Board — Physics");
    await page.fill("#fw-region", "Punjab");
    await page.fill("#fw-grades", "9, 10");
    await page.getByRole("button", { name: /^create$/i }).click();

    await expect(
      page.getByRole("cell", { name: "Matric Punjab — Physics", exact: true })
    ).toBeVisible({ timeout: 5_000 });
  });
});
