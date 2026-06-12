# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: platform-admin-smoke.spec.ts >> Platform Admin smoke test (M-01 acceptance criteria) @smoke @mock >> Full Platform Admin onboarding flow @smoke
- Location: e2e/platform-admin-smoke.spec.ts:34:7

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: locator('p[lang="en"]')
Expected: visible
Timeout: 5000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" with timeout 5000ms
  - waiting for locator('p[lang="en"]')

```

```yaml
- status:
  - img
  - text: Static route
  - button "Hide static indicator":
    - img
- alert
- complementary "Admin navigation":
  - text: IqbalAI Admin
  - navigation "Admin sidebar navigation":
    - list:
      - listitem:
        - link "Languages":
          - /url: /admin/languages
      - listitem:
        - link "Teaching Personas":
          - /url: /admin/personas
      - listitem:
        - link "Exam Syllabi":
          - /url: /admin/exam-syllabi
      - listitem:
        - link "Subscription Tiers":
          - /url: /admin/subscription-tiers
      - listitem:
        - link "ToS & Disclaimer":
          - /url: /admin/tos
      - listitem:
        - link "Platform Library":
          - /url: /admin/library
      - listitem:
        - link "Audit Log":
          - /url: /admin/audit-log
  - button "Switch to English": English
  - button "Switch to اردو": اردو
  - button "Switch to سنڌي": سنڌي
  - button "Switch to پښتو": پښتو
  - button "Sign out"
- banner:
  - button "Notifications"
  - text: admin@iqbalai.test Platform Admin
- main
```

# Test source

```ts
  1   | /**
  2   |  * T-026 — Platform Admin smoke test (E2E @smoke @mock).
  3   |  *
  4   |  * Full M-01 acceptance flow with route mocks (no Authentik / compose required on PR).
  5   |  * Real Authentik + compose bring-up is a manual / nightly concern; API contract
  6   |  * coverage lives in admin-create-real.spec.ts (@smoke @real).
  7   |  */
  8   | import { test, expect, type Page } from "@playwright/test";
  9   | import { installPlatformAdminMocks } from "./helpers/mock-api";
  10  | 
  11  | async function bootstrapAdmin(page: Page) {
  12  |   const state = await installPlatformAdminMocks(page);
  13  |   state.tosAccepted = false;
  14  |   await page.goto("/auth/callback?code=e2e-test-code");
  15  |   return state;
  16  | }
  17  | 
  18  | async function acceptTos(page: Page) {
  19  |   await expect(
  20  |     page.getByRole("dialog", { name: /terms of service/i }),
  21  |   ).toBeVisible({ timeout: 10_000 });
  22  |   const content = page.locator('[aria-label="Terms of Service content"]');
  23  |   await content.evaluate((el: HTMLElement) => el.scrollTo(0, el.scrollHeight));
  24  |   await expect(page.getByRole("button", { name: /i accept/i })).toBeEnabled({
  25  |     timeout: 3_000,
  26  |   });
  27  |   await page.getByRole("button", { name: /i accept/i }).click();
  28  |   await page.waitForURL("**/admin**", { timeout: 10_000 });
  29  | }
  30  | 
  31  | test.describe("Platform Admin smoke test (M-01 acceptance criteria) @smoke @mock", () => {
  32  |   test.setTimeout(120_000);
  33  | 
  34  |   test("Full Platform Admin onboarding flow @smoke", async ({ page }) => {
  35  |     const state = await bootstrapAdmin(page);
  36  |     await acceptTos(page);
  37  | 
  38  |     await expect(page).toHaveURL(/\/admin/);
  39  | 
  40  |     await page.click('a:has-text("Languages")');
  41  |     for (const code of ["en", "ur", "sd", "ps"]) {
> 42  |       await expect(page.locator(`p[lang="${code}"]`)).toBeVisible();
      |                                                       ^ Error: expect(locator).toBeVisible() failed
  43  |     }
  44  | 
  45  |     await page.click('a:has-text("Exam Syllabi")');
  46  |     for (const name of [
  47  |       "Matric Punjab Board",
  48  |       "FSc Punjab Board",
  49  |       "O-Level Cambridge",
  50  |       "A-Level Cambridge",
  51  |     ]) {
  52  |       await page.getByRole("button", { name: /add syllabus/i }).click();
  53  |       await page.fill("#syl-name", name);
  54  |       await page.fill("#syl-exam-board", "Punjab Board");
  55  |       await page.getByRole("button", { name: /create/i }).click();
  56  |       await expect(page.getByRole("cell", { name, exact: true })).toBeVisible({
  57  |         timeout: 5_000,
  58  |       });
  59  |     }
  60  | 
  61  |     await page.click('a:has-text("Teaching Personas")');
  62  |     await expect(page.getByRole("button", { name: /edit prompt/i })).toHaveCount(
  63  |       5,
  64  |       { timeout: 5_000 },
  65  |     );
  66  |     await page.getByRole("button", { name: /edit prompt/i }).first().click();
  67  |     await page.fill("#system_prompt_en", "You are a strict, focused tutor.");
  68  |     await page.getByRole("button", { name: /save changes/i }).click();
  69  |     await expect(page.getByRole("dialog")).not.toBeVisible({ timeout: 3_000 });
  70  | 
  71  |     await page.click('a:has-text("Subscription Tiers")');
  72  |     for (const { name, price, slug, appliesTo } of [
  73  |       { name: "Basic District", price: "5000", slug: "basic-district", appliesTo: "district" },
  74  |       { name: "Premium School", price: "10000", slug: "premium-school", appliesTo: "school" },
  75  |     ]) {
  76  |       await page.getByRole("button", { name: /add tier/i }).click();
  77  |       await page.fill("#tier-name", name);
  78  |       await page.fill("#tier-slug", slug);
  79  |       await page.selectOption("#tier-applies-to", appliesTo);
  80  |       await page.fill("#tier-price", price);
  81  |       await page.getByRole("button", { name: /create/i }).click();
  82  |       await expect(page.getByText(name)).toBeVisible({ timeout: 5_000 });
  83  |     }
  84  | 
  85  |     await page.getByRole("link", { name: "ToS & Disclaimer" }).click();
  86  |     await page
  87  |       .getByRole("main")
  88  |       .getByRole("button", { name: /publish new version/i })
  89  |       .first()
  90  |       .click();
  91  |     await page.fill(
  92  |       "#tos-content",
  93  |       "These are the Terms of Service for IqbalAI. By using this platform you agree to our terms.",
  94  |     );
  95  |     await page.getByRole("button", { name: /^publish$/i }).click();
  96  |     await expect(page.getByRole("dialog")).not.toBeVisible({ timeout: 5_000 });
  97  |     await expect(page.getByText("Version 1")).toBeVisible({ timeout: 5_000 });
  98  | 
  99  |     await page.goto("/admin/tos?tab=disclaimer");
  100 |     await page
  101 |       .getByRole("main")
  102 |       .getByRole("button", { name: /publish new version/i })
  103 |       .first()
  104 |       .click();
  105 |     await page.fill(
  106 |       "#tos-content",
  107 |       "AI outputs may contain errors. Verify with authoritative sources.",
  108 |     );
  109 |     await page.getByRole("button", { name: /^publish$/i }).click();
  110 |     await expect(page.getByRole("dialog")).not.toBeVisible({ timeout: 5_000 });
  111 |     await expect(page.getByText("Version 1")).toBeVisible({ timeout: 5_000 });
  112 | 
  113 |     await page.getByRole("link", { name: "Audit Log" }).click();
  114 |     await page.waitForURL("**/admin/audit-log**");
  115 |     await expect(page.getByRole("heading", { name: "Audit Log", level: 1 })).toBeVisible();
  116 |     expect(state.auditLog.some((e) => e.action === "exam_syllabus.created")).toBe(true);
  117 |     expect(state.auditLog.some((e) => e.action === "tos.published")).toBe(true);
  118 |   });
  119 | 
  120 |   test("ToS decline → logs user out @smoke", async ({ page }) => {
  121 |     await bootstrapAdmin(page);
  122 |     await expect(
  123 |       page.getByRole("dialog", { name: /terms of service/i }),
  124 |     ).toBeVisible({ timeout: 10_000 });
  125 |     await page.getByRole("button", { name: /decline/i }).click();
  126 |     await expect(page.getByRole("heading", { name: /account suspended/i })).toBeVisible({
  127 |       timeout: 10_000,
  128 |     });
  129 |   });
  130 | });
  131 | 
```