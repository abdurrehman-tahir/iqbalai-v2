/**
 * T-058 — Coordinator curriculum upload + topic tree smoke (@smoke).
 */

import { test, expect, type Page, type Route } from "@playwright/test";

const BASE_URL = process.env.E2E_BASE_URL ?? "http://localhost:3000";

function envelope<T>(data: T) {
  return JSON.stringify({ data, message: "ok" });
}

async function installCoordinatorMocks(page: Page) {
  let itemStatus = "ingesting";

  await page.route(
    (url) => url.pathname.includes("/api/v1/"),
    async (route: Route) => {
      const request = route.request();
      const url = new URL(request.url());
      let path = url.pathname.replace("/api/v1", "");
      if (path.length > 1 && path.endsWith("/")) path = path.slice(0, -1);
      const method = request.method();

      if (method === "GET" && path === "/subjects") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: envelope([{ id: "subj-1", name: "Physics", language: "en", status: "active" }]),
        });
        return;
      }

      if (method === "GET" && path === "/grades") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: envelope([{ id: "grade-9", name: "Grade 9", level_ordinal: 9, status: "active" }]),
        });
        return;
      }

      if (method === "POST" && path === "/school/library") {
        await route.fulfill({
          status: 202,
          contentType: "application/json",
          body: envelope({
            item: {
              id: "curriculum-item-1",
              school_id: "school-1",
              title: "Punjab Physics Grade 9",
              content_type: "curriculum",
              language: "en",
              subject_id: "subj-1",
              grade_level_ordinal: 9,
              storage_key: "school-library/school-1/curriculum.pdf",
              sha256: "a".repeat(64),
              ingestion_status: "pending",
              topic_tree_jsonb: null,
              created_by: "coord-1",
              visibility: "school_public",
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

      if (method === "GET" && path === "/school/library/curriculum-item-1") {
        if (itemStatus === "ingesting") {
          itemStatus = "available";
        }
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: envelope({
            id: "curriculum-item-1",
            school_id: "school-1",
            title: "Punjab Physics Grade 9",
            content_type: "curriculum",
            language: "en",
            subject_id: "subj-1",
            grade_level_ordinal: 9,
            storage_key: "school-library/school-1/curriculum.pdf",
            sha256: "a".repeat(64),
            ingestion_status: itemStatus,
            topic_tree_jsonb:
              itemStatus === "available"
                ? {
                    chapters: [
                      {
                        title: "Mechanics",
                        sections: [{ title: "Motion", sub_topics: ["Speed"] }],
                      },
                    ],
                    parse_degraded: false,
                  }
                : null,
            created_by: "coord-1",
            visibility: "school_public",
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

test.describe("Coordinator curriculum upload @smoke", () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      sessionStorage.setItem("iqbalai_access_token", "e2e-coordinator-token");
      sessionStorage.setItem(
        "iqbalai_user",
        JSON.stringify({
          email: "coord@test.com",
          role: "coordinator",
          school_id: "school-1",
        }),
      );
    });
    await installCoordinatorMocks(page);
  });

  test("uploads curriculum and shows topic tree when available", async ({ page }) => {
    await page.goto(`${BASE_URL}/coordinator/library/curriculum/upload`);

    await expect(page.getByRole("heading", { name: /Upload curriculum/i })).toBeVisible();
    await expect(page.getByText(/always visible to everyone/i)).toBeVisible();

    await page.getByLabel(/^Title/i).fill("Punjab Physics Grade 9");
    await expect(page.getByLabel(/Subject/i).locator('option[value="subj-1"]')).toHaveCount(1);
    await page.getByLabel(/Subject/i).selectOption("subj-1");
    await page.getByLabel(/Grade/i).selectOption("9");
    await page.getByLabel(/Curriculum PDF/i).setInputFiles({
      name: "curriculum.pdf",
      mimeType: "application/pdf",
      buffer: Buffer.from("%PDF-1.4 test"),
    });

    await page.getByRole("button", { name: /Upload curriculum/i }).click();

    await expect(page).toHaveURL(/\/coordinator\/library\/curriculum\/curriculum-item-1$/);
    await expect(
      page.getByRole("status").filter({ hasText: /Available|Ingesting/i }),
    ).toHaveText(/Available|Ingesting/i, {
      timeout: 15_000,
    });
    await expect(page.getByText("Mechanics")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("School public")).toBeVisible();
  });
});
