/**
 * T-231 — M-01 navigation reachability smoke (E2E, @smoke).
 *
 * Proves every M-01 admin section is reachable from nav and renders real content.
 */
import { test, expect, type Page } from "@playwright/test";
import { installPlatformAdminMocks } from "./helpers/mock-api";

// Six M-01 sections per flow-1 §2/§4 (Platform Library is M-01 T-024 — covered separately).
const NAV = [
  { name: "Languages", path: "/admin/languages" },
  { name: "Teaching Personas", path: "/admin/personas" },
  { name: "Exam Syllabi", path: "/admin/exam-syllabi" },
  { name: "Subscription Tiers", path: "/admin/subscription-tiers" },
  { name: "ToS & Disclaimer", path: "/admin/tos" },
  { name: "Audit Log", path: "/admin/audit-log" },
] as const;

async function seedPlatformAdmin(page: Page) {
  await installPlatformAdminMocks(page);
  await page.context().addCookies([
    {
      name: "iqbalai_access",
      value: "dev-access-user-platform-admin-1",
      domain: "localhost",
      path: "/",
      httpOnly: true,
      sameSite: "Lax" as const,
    },
  ]);
  await page.addInitScript(() => {
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

test.describe("M-01 admin navigation reachability (T-231) @smoke @mock", () => {
  test("each nav item reaches a page with real content @smoke", async ({ page }) => {
    await seedPlatformAdmin(page);
    await page.goto("/admin/languages");

    const sidebar = page.getByRole("navigation", { name: "Admin sidebar navigation" });
    await expect(sidebar).toBeVisible();

    for (const { name } of NAV) {
      await expect(sidebar.getByRole("link", { name })).toBeVisible();
    }

    for (const { name, path } of NAV) {
      await sidebar.getByRole("link", { name }).click();
      await page.waitForURL(`**${path}`);
      await expect(
        page.getByRole("main").getByRole("heading", { level: 1 }).first(),
      ).toBeVisible();
    }

    // Disclaimer tab under ToS renders its own heading.
    await sidebar.getByRole("link", { name: "ToS & Disclaimer" }).click();
    await page.getByRole("button", { name: "Disclaimer" }).click();
    await expect(
      page.getByRole("main").getByRole("heading", { level: 1 }).first(),
    ).toBeVisible();
  });
});
