/**
 * M-07a T-247 — real OIDC coverage (@auth @real).
 *
 * This suite deliberately makes no route mocks. The basic cases require a
 * running API at NEXT_PUBLIC_API_URL (default: http://localhost:8000/api/v1).
 * Role-login cases additionally require the corresponding
 * E2E_OIDC_<ROLE>_EMAIL and E2E_OIDC_<ROLE>_PASSWORD variables; see README.md.
 */
import { expect, test, type Page } from "@playwright/test";

const API_BASE = (
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1"
).replace(/\/$/, "");

const ROLE_CASES = [
  { env: "PLATFORM_ADMIN", dashboard: "/admin" },
  { env: "DISTRICT_ADMIN", dashboard: "/admin/district/schools" },
  { env: "SCHOOL_ADMIN", dashboard: "/school/admin" },
  { env: "COORDINATOR", dashboard: "/coordinator" },
  { env: "TEACHER", dashboard: "/teacher" },
  { env: "STUDENT", dashboard: "/student" },
  { env: "PARENT", dashboard: "/parent" },
  { env: "INDEPENDENT_TEACHER", dashboard: "/independent/teacher" },
  { env: "INDEPENDENT_STUDENT", dashboard: "/independent/student" },
] as const;

async function apiReachable(): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE}/health`);
    return response.ok;
  } catch {
    return false;
  }
}

async function startOidcLogin(page: Page): Promise<void> {
  await page.goto("/login");
  const apiLoginResponse = page.waitForResponse(
    (response) =>
      response.url().startsWith(`${API_BASE}/auth/login`) &&
      response.status() === 302
  );

  await page.getByRole("button").click();
  const response = await apiLoginResponse;
  const location = response.headers().location;

  expect(location, "API login must redirect to the configured OIDC provider").toBeTruthy();
  const oidcUrl = new URL(location!);
  expect(oidcUrl.searchParams.get("state")).toBeTruthy();
  expect(oidcUrl.searchParams.get("code_challenge")).toBeTruthy();
}

test.describe("Authentication against real API and OIDC @auth @real", () => {
  test.beforeEach(async () => {
    test.skip(
      !(await apiReachable()),
      `API is not reachable at ${API_BASE}; set NEXT_PUBLIC_API_URL to the real API base URL`
    );
  });

  test("unauthenticated protected API access returns 401", async ({ request }) => {
    const response = await request.get(`${API_BASE}/auth/me`);

    expect(response.status()).toBe(401);
  });

  test("login page enters OIDC through the API-owned endpoint", async ({ page }) => {
    await startOidcLogin(page);
  });

  for (const { env, dashboard } of ROLE_CASES) {
    test(`OIDC login reaches ${dashboard} for ${env} @auth @real`, async ({ page }) => {
      const emailVariable = `E2E_OIDC_${env}_EMAIL`;
      const passwordVariable = `E2E_OIDC_${env}_PASSWORD`;
      const email = process.env[emailVariable];
      const password = process.env[passwordVariable];

      test.skip(
        !email || !password,
        `Real OIDC credentials are required: ${emailVariable} and ${passwordVariable}`
      );
      if (!email || !password) return;

      await startOidcLogin(page);
      await page.locator('input[name="username"], input[name="email"]').first().fill(email);
      await page.locator('input[name="password"]').fill(password);
      await page.locator('button[type="submit"]').click();

      await expect(page).toHaveURL(new RegExp(`${dashboard}(?:[/?#]|$)`));
    });
  }
});
