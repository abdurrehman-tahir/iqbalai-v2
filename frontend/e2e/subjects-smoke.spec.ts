/**
 * T-041 — Coordinator Subjects smoke test (E2E, @smoke).
 *
 * Self-contained: the Subjects + /auth/me API is mocked inline (no live backend).
 * Since T-245 the session is an HttpOnly cookie and the shell reads "who am I"
 * from GET /auth/me (mocked here), so no sessionStorage seeding is needed (T-247).
 * Exercises the create flow and asserts the new subject renders.
 *
 * Run:
 *   pnpm exec playwright test e2e/subjects-smoke.spec.ts
 */

import { test, expect, type Page, type Route } from "@playwright/test";

const BASE_URL = process.env.E2E_BASE_URL ?? "http://localhost:3000";

interface MockSubject {
  id: string;
  school_id: string;
  name: string;
  language: string;
  status: "active" | "archived";
  created_at: string;
}

function envelope<T>(data: T) {
  return JSON.stringify({ data, message: "ok" });
}

async function installCoordinatorMocks(page: Page) {
  const subjects: MockSubject[] = [];

  await page.route(
    (url) => url.pathname.includes("/api/v1/"),
    async (route: Route) => {
      const request = route.request();
      const url = new URL(request.url());
      let path = url.pathname.replace("/api/v1", "");
      if (path.length > 1 && path.endsWith("/")) path = path.slice(0, -1);
      const method = request.method();

      // T-247: shell resolves "who am I" via GET /auth/me (cookie session)
      // since T-245 — mock it or useCurrentUser() never resolves.
      if (method === "GET" && path === "/auth/me") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: envelope({
            user_id: "user-coordinator-1",
            email: "coordinator@iqbalai.test",
            role: "coordinator",
            tenant_type: "school",
            school_id: "school-1",
            district_id: null,
          }),
        });
        return;
      }

      if (method === "GET" && path === "/users/me") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: envelope({
            id: "user-coordinator-1",
            email: "coordinator@iqbalai.test",
            display_name: "Coordinator",
            role: "coordinator",
            status: "active",
            scoped_ids: "9,10",
            district_id: null,
            school_id: "school-1",
            created_at: new Date().toISOString(),
          }),
        });
        return;
      }

      if (method === "GET" && path === "/subjects") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: envelope(subjects),
        });
        return;
      }

      if (method === "POST" && path === "/subjects") {
        const body = (await request.postDataJSON()) as { name: string; language: string };
        const subject: MockSubject = {
          id: `subject-${subjects.length + 1}`,
          school_id: "school-1",
          name: body.name,
          language: body.language,
          status: "active",
          created_at: new Date().toISOString(),
        };
        subjects.push(subject);
        await route.fulfill({
          status: 201,
          contentType: "application/json",
          body: envelope(subject),
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

test.describe("Coordinator Subjects @smoke", () => {
  test("Coordinator creates a subject and sees it listed", async ({ page }) => {
    await installCoordinatorMocks(page);

    await page.goto(`${BASE_URL}/coordinator/subjects`);

    // Empty state first, then create.
    await page
      .getByRole("button", { name: /add subject/i })
      .first()
      .click();
    await page.fill("#subject-name", "Physics");
    await page.getByRole("button", { name: /^create$/i }).click();

    await expect(page.getByRole("cell", { name: "Physics", exact: true })).toBeVisible({
      timeout: 5_000,
    });
  });
});
