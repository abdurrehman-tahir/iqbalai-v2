/**
 * T-092 — Platform Admin Exam Frameworks smoke test (E2E, @smoke).
 *
 * Self-contained: the frameworks + /auth/me API is mocked inline (no live
 * backend). Since T-245 the session is an HttpOnly cookie and the shell reads
 * "who am I" from GET /auth/me (mocked here), so no sessionStorage seeding is
 * needed (T-247). Drives nav → create → row-visible, asserting the page is
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
  subject_slug: string;
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

async function installAdminMocks(page: Page, seed: MockFramework[] = []) {
  const frameworks: MockFramework[] = [...seed];
  const plan = {
    id: "plan-1",
    framework_id: "framework-pending",
    version: 1,
    content_jsonb: {
      topics: [{ topic_name: "Kinematics" }, { topic_name: "Dynamics" }],
      weekly_pacing: [{}, {}, {}],
      exam_strategy: {},
    },
    sources_cited_jsonb: [{ url: "https://ex.com", title: "Past papers" }],
    generated_at: new Date().toISOString(),
    approved_by: null,
    approved_at: null,
    status: "pending_approval",
    reviewer_notes: null,
    created_at: new Date().toISOString(),
  };

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
            user_id: "user-platform-admin-1",
            email: "admin@iqbalai.test",
            role: "platform_admin",
            tenant_type: "school",
            school_id: null,
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
          subject_slug: string;
          region: string;
          target_grade_range: number[];
          language: string;
        };
        const framework: MockFramework = {
          id: `framework-${frameworks.length + 1}`,
          name: body.name,
          exam_target: body.exam_target,
          subject_slug: body.subject_slug,
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

      // T-093: trigger the AI research run — flips the framework to RESEARCHING
      // and returns a RUNNING job (202 Accepted).
      const researchMatch = path.match(/^\/exam-frameworks\/([^/]+)\/research$/);
      if (method === "POST" && researchMatch) {
        const target = frameworks.find((f) => f.id === researchMatch[1]);
        if (target) target.status = "researching";
        await route.fulfill({
          status: 202,
          contentType: "application/json",
          body: envelope({
            id: "job-1",
            framework_id: researchMatch[1],
            status: "running",
            cost_usd: 0,
            sources_count: 0,
            error: null,
            study_plan_id: null,
            started_at: new Date().toISOString(),
            finished_at: null,
            created_at: new Date().toISOString(),
          }),
        });
        return;
      }

      // T-094: review the pending study plan.
      const planMatch = path.match(/^\/exam-frameworks\/([^/]+)\/plan$/);
      if (method === "GET" && planMatch) {
        const target = frameworks.find((f) => f.id === planMatch[1]);
        if (!target || target.status !== "pending_approval") {
          await route.fulfill({
            status: 404,
            contentType: "application/json",
            body: JSON.stringify({
              error: { code: "NOT_FOUND", message: "No plan pending approval" },
            }),
          });
          return;
        }
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: envelope({ ...plan, framework_id: target.id }),
        });
        return;
      }

      // T-094: approve → framework PUBLISHED, plan APPROVED.
      const approveMatch = path.match(/^\/exam-frameworks\/([^/]+)\/approve$/);
      if (method === "POST" && approveMatch) {
        const target = frameworks.find((f) => f.id === approveMatch[1]);
        if (target) target.status = "published";
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: envelope({ ...plan, framework_id: approveMatch[1], status: "approved" }),
        });
        return;
      }

      // T-094: reject → framework back to DRAFT with reviewer notes.
      const rejectMatch = path.match(/^\/exam-frameworks\/([^/]+)\/reject$/);
      if (method === "POST" && rejectMatch) {
        const target = frameworks.find((f) => f.id === rejectMatch[1]);
        if (target) target.status = "draft";
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: envelope({ ...plan, framework_id: rejectMatch[1], status: "draft" }),
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

test.describe("Platform Admin Exam Frameworks @smoke", () => {
  test("Admin reaches frameworks from nav, creates one, and sees it listed", async ({ page }) => {
    await installAdminMocks(page);

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
    await page.fill("#fw-subject-slug", "physics");
    await page.fill("#fw-region", "Punjab");
    await page.fill("#fw-grades", "9, 10");
    await page.getByRole("button", { name: /^create$/i }).click();

    await expect(
      page.getByRole("cell", { name: "Matric Punjab — Physics", exact: true })
    ).toBeVisible({ timeout: 5_000 });

    // T-093: trigger AI research on the DRAFT row → the status flips to Researching.
    await page
      .getByRole("button", { name: /run ai research/i })
      .first()
      .click();
    await expect(page.getByText(/researching/i).first()).toBeVisible({ timeout: 5_000 });
  });

  test("Admin reviews a pending plan and approves it → framework publishes", async ({
    page,
  }) => {
    const pending: MockFramework = {
      id: "framework-pending",
      name: "Matric Sindh — Chemistry",
      exam_target: "Matric Sindh Board — Chemistry",
      subject_slug: "chemistry",
      region: "Sindh",
      target_grade_range: [9, 10],
      language: "en",
      status: "pending_approval",
      created_by: "user-platform-admin-1",
      created_at: new Date().toISOString(),
    };
    await installAdminMocks(page, [pending]);

    await page.goto(`${BASE_URL}/admin/exam-frameworks`);
    await expect(
      page.getByRole("cell", { name: "Matric Sindh — Chemistry", exact: true })
    ).toBeVisible({ timeout: 5_000 });

    // Open the review surface → plan content + cited sources render.
    await page
      .getByRole("button", { name: /review study plan/i })
      .first()
      .click();
    await expect(page.getByText("Kinematics")).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText("Past papers")).toBeVisible();

    // Approve & publish → row status flips to Published.
    await page.getByRole("button", { name: /approve & publish/i }).click();
    await expect(page.getByText(/published/i).first()).toBeVisible({ timeout: 5_000 });
  });
});
