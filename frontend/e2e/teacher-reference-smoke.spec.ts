/**
 * T-059 — Teacher reference upload + privacy toggle smoke (@smoke).
 */

import { test, expect, type Page, type Route } from "@playwright/test";

const BASE_URL = process.env.E2E_BASE_URL ?? "http://localhost:3000";

function envelope<T>(data: T) {
  return JSON.stringify({ data, message: "ok" });
}

async function installTeacherReferenceMocks(page: Page) {
  let itemStatus = "ingesting";
  let visibility = "private";

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

      if (method === "POST" && path === "/school/library/") {
        const visibilityParam = url.searchParams.get("visibility");
        visibility = visibilityParam === "school_public" ? "school_public" : "private";
        await route.fulfill({
          status: 202,
          contentType: "application/json",
          body: envelope({
            item: {
              id: "reference-item-1",
              school_id: "school-1",
              title: "Physics Notes",
              content_type: "reference",
              language: "en",
              subject_id: null,
              grade_level_ordinal: null,
              storage_key: "school-library/school-1/notes.pdf",
              sha256: "a".repeat(64),
              ingestion_status: "pending",
              topic_tree_jsonb: null,
              created_by: "teacher-1",
              visibility,
              created_at: "2026-06-16T00:00:00Z",
              updated_at: "2026-06-16T00:00:00Z",
            },
            storage_deduplicated: false,
            selection_created: true,
            message: "ok",
          }),
        });
        return;
      }

      if (method === "POST" && path === "/school/library/reference-item-1/publish") {
        visibility = "school_public";
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: envelope({
            id: "reference-item-1",
            school_id: "school-1",
            title: "Physics Notes",
            content_type: "reference",
            language: "en",
            subject_id: null,
            grade_level_ordinal: null,
            storage_key: "school-library/school-1/notes.pdf",
            sha256: "a".repeat(64),
            ingestion_status: itemStatus,
            topic_tree_jsonb: null,
            created_by: "teacher-1",
            visibility: "school_public",
            created_at: "2026-06-16T00:00:00Z",
            updated_at: "2026-06-16T00:00:00Z",
          }),
        });
        return;
      }

      if (method === "GET" && path === "/school/library/reference-item-1") {
        if (itemStatus === "ingesting") {
          itemStatus = "available";
        }
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: envelope({
            id: "reference-item-1",
            school_id: "school-1",
            title: "Physics Notes",
            content_type: "reference",
            language: "en",
            subject_id: null,
            grade_level_ordinal: null,
            storage_key: "school-library/school-1/notes.pdf",
            sha256: "a".repeat(64),
            ingestion_status: itemStatus,
            topic_tree_jsonb: null,
            created_by: "teacher-1",
            visibility,
            created_at: "2026-06-16T00:00:00Z",
            updated_at: "2026-06-16T00:00:00Z",
          }),
        });
        return;
      }

      await route.continue();
    },
  );
}

test.describe("Teacher reference upload @smoke", () => {
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
    await installTeacherReferenceMocks(page);
  });

  test("uploads private reference by default and can publish to school", async ({ page }) => {
    await page.goto(`${BASE_URL}/teacher/library/reference/upload`);

    await expect(page.getByRole("heading", { name: /Upload reference book/i })).toBeVisible();
    await expect(page.getByLabel(/Make available to the school/i)).not.toBeChecked();

    await page.getByLabel(/^Title/i).fill("Physics Notes");
    await page.getByLabel(/Reference PDF/i).setInputFiles({
      name: "notes.pdf",
      mimeType: "application/pdf",
      buffer: Buffer.from("%PDF-1.4 test"),
    });

    await page.getByRole("button", { name: /Upload reference book/i }).click();

    await expect(page).toHaveURL(/\/teacher\/library\/reference\/reference-item-1$/);
    await expect(page.getByText("Private — only you")).toBeVisible({ timeout: 15_000 });

    await page.getByRole("button", { name: /Make available to school/i }).click();

    await expect(page.getByText("School public")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText(/cannot be made private/i)).toBeVisible();
  });

  test("uploads public reference when privacy toggle is checked", async ({ page }) => {
    await page.goto(`${BASE_URL}/teacher/library/reference/upload`);

    await page.getByLabel(/^Title/i).fill("Shared Notes");
    await page.getByLabel(/Make available to the school/i).check();
    await page.getByLabel(/Reference PDF/i).setInputFiles({
      name: "notes.pdf",
      mimeType: "application/pdf",
      buffer: Buffer.from("%PDF-1.4 test"),
    });

    await page.getByRole("button", { name: /Upload reference book/i }).click();

    await expect(page).toHaveURL(/\/teacher\/library\/reference\/reference-item-1$/);
    await expect(page.getByText("School public")).toBeVisible({ timeout: 15_000 });
  });
});
