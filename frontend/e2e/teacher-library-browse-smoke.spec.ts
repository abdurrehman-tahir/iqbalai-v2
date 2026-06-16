/**
 * T-060 — Teacher content library browse + filters smoke (@smoke).
 */

import { test, expect, type Page, type Route } from "@playwright/test";

const BASE_URL = process.env.E2E_BASE_URL ?? "http://localhost:3000";

function envelope<T>(data: T) {
  return JSON.stringify({ data, message: "ok" });
}

async function installBrowseMocks(page: Page) {
  await page.route(
    (url) => url.pathname.includes("/api/v1/"),
    async (route: Route) => {
      const request = route.request();
      const url = new URL(request.url());
      let path = url.pathname.replace("/api/v1", "");
      if (path.length > 1 && path.endsWith("/")) path = path.slice(0, -1);
      const method = request.method();

      if (method === "GET" && path === "/subjects/") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: envelope([{ id: "subj-1", name: "Physics", language: "en", status: "active" }]),
        });
        return;
      }

      if (method === "GET" && path === "/grades/") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: envelope([{ id: "grade-9", name: "Grade 9", level_ordinal: 9, status: "active" }]),
        });
        return;
      }

      if (method === "GET" && path === "/school/library") {
        const titleFilter = url.searchParams.get("title");
        const items = [
          {
            id: "curriculum-item-1",
            school_id: "school-1",
            title: "Punjab Physics Grade 9",
            content_type: "curriculum",
            language: "en",
            subject_id: "subj-1",
            grade_level_ordinal: 9,
            storage_key: "school-library/school-1/curriculum.pdf",
            sha256: "a".repeat(64),
            ingestion_status: "available",
            topic_tree_jsonb: null,
            created_by: "coord-1",
            visibility: "school_public",
            created_at: "2026-06-16T00:00:00Z",
            updated_at: "2026-06-16T00:00:00Z",
          },
          {
            id: "reference-item-1",
            school_id: "school-1",
            title: "My Notes",
            content_type: "reference",
            language: "en",
            subject_id: null,
            grade_level_ordinal: null,
            storage_key: "school-library/school-1/notes.pdf",
            sha256: "b".repeat(64),
            ingestion_status: "pending",
            topic_tree_jsonb: null,
            created_by: "teacher-1",
            visibility: "private",
            created_at: "2026-06-16T00:00:00Z",
            updated_at: "2026-06-16T00:00:00Z",
          },
        ];
        const filtered = titleFilter
          ? items.filter((item) => item.title.toLowerCase().includes(titleFilter.toLowerCase()))
          : items;

        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: envelope({ items: filtered, total: filtered.length }),
        });
        return;
      }

      await route.continue();
    },
  );
}

test.describe("Teacher content library browse @smoke", () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      sessionStorage.setItem("iqbalai_access_token", "e2e-teacher-token");
      sessionStorage.setItem(
        "iqbalai_user",
        JSON.stringify({
          user_id: "teacher-1",
          email: "teacher@test.com",
          role: "teacher",
          school_id: "school-1",
        }),
      );
    });
    await installBrowseMocks(page);
  });

  test("lists library items and filters by title", async ({ page }) => {
    await page.goto(`${BASE_URL}/teacher/library`);

    await expect(page.getByRole("heading", { name: /Content Library/i })).toBeVisible();
    await expect(page.getByText("Punjab Physics Grade 9")).toBeVisible();
    await expect(page.getByText("My Notes")).toBeVisible();
    await expect(page.getByText("Available")).toBeVisible();
    await expect(page.getByText("Pending")).toBeVisible();

    await page.getByLabel(/Search by title/i).fill("Physics");
    await expect(page.getByText("Punjab Physics Grade 9")).toBeVisible();
    await expect(page.getByText("My Notes")).not.toBeVisible();
  });
});
