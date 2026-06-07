/**
 * T-227 — App shell + role-aware nav smoke (E2E, @smoke).
 *
 * Proves the authenticated /admin shell is the single shell every page plugs
 * into and that NO nav item is an orphan: the shell renders, and every
 * role-filtered nav item routes to a page that renders real content.
 *
 * Runs fully offline — `installPlatformAdminMocks` stubs the API and we seed a
 * platform_admin session into sessionStorage via addInitScript, so the PR-time
 * `pnpm e2e --grep @smoke` job (dev server only, no live backend) can run it.
 */
import { test, expect, type Page } from "@playwright/test";
import { installPlatformAdminMocks } from "./helpers/mock-api";

// Each nav item → the accessible link name (English default locale) and the
// route it must reach. Mirrors NAV_ITEMS in AdminShell.tsx (flow-1 §4).
const NAV = [
  { name: "Languages", path: "/admin/languages" },
  { name: "Teaching Personas", path: "/admin/personas" },
  { name: "Exam Syllabi", path: "/admin/exam-syllabi" },
  { name: "Subscription Tiers", path: "/admin/subscription-tiers" },
  { name: "ToS & Disclaimer", path: "/admin/tos" },
  { name: "Platform Library", path: "/admin/library" },
  { name: "Audit Log", path: "/admin/audit-log" },
] as const;

async function seedPlatformAdmin(page: Page) {
  await installPlatformAdminMocks(page);
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
      }),
    );
  });
}

test.describe("Admin shell + role-aware nav (T-227)", () => {
  test("shell renders with the platform_admin's nav and every item reaches content @smoke", async ({
    page,
  }) => {
    await seedPlatformAdmin(page);
    await page.goto("/admin/languages");

    // Shell chrome renders.
    const sidebar = page.getByRole("navigation", { name: "Admin sidebar navigation" });
    await expect(sidebar).toBeVisible();

    // Role-filtered nav: all seven platform_admin links present.
    for (const { name } of NAV) {
      await expect(sidebar.getByRole("link", { name })).toBeVisible();
    }

    // Every nav item routes to a page that renders real content (a heading).
    for (const { name, path } of NAV) {
      await sidebar.getByRole("link", { name }).click();
      await page.waitForURL(`**${path}`);
      await expect(
        page.getByRole("main").getByRole("heading").first(),
      ).toBeVisible();
    }
  });
});
