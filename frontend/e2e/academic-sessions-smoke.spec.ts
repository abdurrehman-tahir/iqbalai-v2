/**
 * T-042 — Coordinator academic session smoke test (E2E, @smoke).
 */

import { test, expect, type Page, type Route } from "@playwright/test";

const BASE_URL = process.env.E2E_BASE_URL ?? "http://localhost:3000";

interface MockSession {
  id: string;
  school_id: string;
  label: string;
  is_active: boolean;
  start_date: string | null;
  end_date: string | null;
  created_at: string;
}

function envelope<T>(data: T) {
  return JSON.stringify({ data, message: "ok" });
}

async function installMocks(page: Page) {
  const sessions: MockSession[] = [];

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
            scoped_ids: "Grade 9,Grade 10",
            district_id: null,
            school_id: "school-1",
            created_at: new Date().toISOString(),
          }),
        });
        return;
      }

      if (method === "GET" && path === "/academic-sessions/active") {
        const active = sessions.find((s) => s.is_active) ?? null;
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: envelope({
            label: active?.label ?? null,
            session: active,
          }),
        });
        return;
      }

      if (method === "GET" && path === "/academic-sessions") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: envelope(sessions),
        });
        return;
      }

      if (method === "POST" && path === "/academic-sessions") {
        const body = (await request.postDataJSON()) as {
          label: string;
          set_active?: boolean;
        };
        sessions.forEach((s) => {
          s.is_active = false;
        });
        const session: MockSession = {
          id: `session-${sessions.length + 1}`,
          school_id: "school-1",
          label: body.label,
          is_active: body.set_active ?? false,
          start_date: null,
          end_date: null,
          created_at: new Date().toISOString(),
        };
        sessions.push(session);
        await route.fulfill({
          status: 201,
          contentType: "application/json",
          body: envelope(session),
        });
        return;
      }

      await route.fulfill({ status: 404, body: JSON.stringify({ error: "not mocked" }) });
    }
  );
}

test.describe("Coordinator academic sessions @smoke", () => {
  test("create and display active session", async ({ page }) => {
    await installMocks(page);
    await page.goto(`${BASE_URL}/coordinator/subjects`);

    await expect(page.getByText(/no active session/i)).toBeVisible();
    await page.getByRole("button", { name: /manage sessions/i }).click();
    await page.getByLabel(/session label/i).fill("2025-2026");
    await page.getByRole("button", { name: /create & activate/i }).click();

    await expect(page.getByText(/session:.*2025-2026/i)).toBeVisible();
  });
});
