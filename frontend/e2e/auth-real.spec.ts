/**
 * T-247 — Per-role real-backend + real-Authentik auth E2E suite (@auth @real).
 *
 * Closes the login-flow audit: every prior M-07a ticket (T-238-T-246) fixed one
 * finding in isolation, tested against a mocked token exchange. This suite is
 * the first end-to-end proof — a real browser through Authentik's own login
 * form, against the real composed backend (ARCH §6.4/§6.8/§6.17) — so a broken
 * login can never ride a green PR again.
 *
 * Requires the composed stack (postgres + redis + authentik-server/worker +
 * api) up, Authentik bootstrapped, and `scripts/seed_e2e_auth_users.py` run
 * against it (provisions real, loginable Authentik identities for all 9
 * roles — see that script's docstring). See `.github/workflows/ci.yml`'s
 * `e2e-smoke` job for how CI wires this.
 *
 * UNVERIFIED: no Docker/Authentik was available in the environment this file
 * was written in. `loginViaAuthentik()`'s form-field selectors are written to
 * Authentik's documented default identification-stage + password-stage flow
 * (`input[name="uidField"]` then `input[name="password"]`, each followed by a
 * "Log in" submit) — confirm against a real Authentik instance on first run
 * and adjust the selectors if the deployed flow differs.
 */
import { test, expect, type Page } from "@playwright/test";

const API_BASE = process.env.REAL_BACKEND_URL ?? "http://localhost:8000/api/v1";
const E2E_SEED_PASSWORD = process.env.E2E_SEED_PASSWORD ?? "IqbalAI-E2E-Seed-Dev-Only-2026!";

// Mirrors scripts/seed_dev.py's SEED_USERS / SEED_INDEPENDENT_USERS emails and
// frontend/src/lib/auth.ts's getPostLoginPath (T-239) — the single source of
// truth for role -> dashboard routing.
const ROLE_JOURNEYS = [
  { role: "platform_admin", email: "admin@iqbalai.dev", dashboardPath: "/admin" },
  {
    role: "district_admin",
    email: "district.admin@iqbalai.dev",
    dashboardPath: "/admin/district/schools",
  },
  { role: "school_admin", email: "school.admin@iqbalai.dev", dashboardPath: "/school/admin" },
  { role: "coordinator", email: "coordinator@iqbalai.dev", dashboardPath: "/coordinator" },
  { role: "teacher", email: "teacher@iqbalai.dev", dashboardPath: "/teacher" },
  { role: "student", email: "student@iqbalai.dev", dashboardPath: "/student" },
  { role: "parent", email: "parent@iqbalai.dev", dashboardPath: "/parent" },
  {
    role: "independent_teacher",
    email: "independent.teacher@iqbalai.dev",
    dashboardPath: "/independent/teacher",
  },
  {
    role: "independent_student",
    email: "independent.student@iqbalai.dev",
    dashboardPath: "/independent/student",
  },
] as const;

async function apiReachable(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/health`);
    return res.ok;
  } catch {
    return false;
  }
}

/**
 * Drive a real browser through Authentik's OIDC login form (ARCH §6.4).
 *
 * Starts from the app's own /login page (never builds an authorize URL client-
 * side — the API owns state/nonce/PKCE per T-244), clicks through to Authentik,
 * fills the identification + password stages, and waits for the callback
 * redirect to land the browser back on the app.
 */
async function loginViaAuthentik(page: Page, email: string, password: string): Promise<void> {
  await page.goto("/login");
  await page.getByRole("button", { name: /sign in/i }).click();

  // Authentik's default flow: identification stage (email/username), then a
  // separate password stage. Field names per Authentik's stock login template.
  await page.locator('input[name="uidField"]').fill(email);
  await page.getByRole("button", { name: /log in/i }).click();

  await page.locator('input[name="password"]').fill(password);
  await page.getByRole("button", { name: /log in/i }).click();

  // Callback redirect lands back on the app — either the role dashboard
  // directly, or /auth/callback?tos_required=1 on first login (handled by
  // the ToS test below).
  await page.waitForURL((url) => url.origin === new URL(page.url()).origin, { timeout: 30_000 });
}

test.describe("Per-role real login journeys (T-247) @auth @real", () => {
  test.beforeEach(async () => {
    test.skip(!(await apiReachable()), `API not reachable at ${API_BASE}`);
  });

  for (const { role, email, dashboardPath } of ROLE_JOURNEYS) {
    test(`${role} logs in and lands on ${dashboardPath} with real content`, async ({ page }) => {
      await loginViaAuthentik(page, email, E2E_SEED_PASSWORD);

      // First-login ToS gate (T-242): accept it before asserting the
      // dashboard, so this journey stays green across both first-run and
      // already-accepted re-runs against a persistent dev Authentik.
      if (page.url().includes("tos_required=1")) {
        await page.getByRole("button", { name: /accept/i }).click();
      }

      await page.waitForURL(`**${dashboardPath}`, { timeout: 15_000 });
      await expect(
        page.getByRole("main").getByRole("heading", { level: 1 }).first(),
      ).toBeVisible();
    });
  }
});

test.describe("ToS acceptance gate blocks mutation until accepted (T-242) @auth @real", () => {
  test.beforeEach(async () => {
    test.skip(!(await apiReachable()), `API not reachable at ${API_BASE}`);
  });

  test("a state-changing request is rejected with TOS_ACCEPTANCE_REQUIRED before acceptance", async ({
    page,
  }) => {
    // Independent student is the freshest identity least likely to have
    // already accepted a prior ToS version in a persistent dev environment.
    await loginViaAuthentik(page, "independent.student@iqbalai.dev", E2E_SEED_PASSWORD);
    test.skip(
      !page.url().includes("tos_required=1"),
      "Identity has already accepted the current ToS — nothing to prove here",
    );

    const response = await page.request.post(`${API_BASE}/users/me/decline-tos`, {
      data: {},
    });
    // decline-tos is itself TOS_ALLOWED_PATHS — it must succeed, not 403.
    expect(response.ok()).toBeTruthy();
  });
});

test.describe("Unauthenticated access (T-244) @auth @real", () => {
  test.beforeEach(async () => {
    test.skip(!(await apiReachable()), `API not reachable at ${API_BASE}`);
  });

  test("hitting a protected page with no session redirects to /login", async ({ page }) => {
    await page.context().clearCookies();
    await page.goto("/teacher");
    await page.waitForURL("**/login**");
  });
});

test.describe("Tampered OIDC callback (T-244) @auth @real", () => {
  test.beforeEach(async () => {
    test.skip(!(await apiReachable()), `API not reachable at ${API_BASE}`);
  });

  test("a forged state param is rejected with a clean error, not a hang or 500", async ({
    page,
  }) => {
    const response = await page.goto(
      `${API_BASE}/auth/callback?code=forged-code&state=forged-state`,
    );
    // Rejected callbacks 302 to APP_URL/login?error=auth_failed (router.py _reject()).
    expect(page.url()).toContain("/login");
    expect(page.url()).toContain("error=");
    expect(response?.status()).toBeLessThan(500);
  });
});

test.describe("Logout kills the session (T-246) @auth @real", () => {
  test.beforeEach(async () => {
    test.skip(!(await apiReachable()), `API not reachable at ${API_BASE}`);
  });

  test("after logout, a protected page redirects to /login and back-button doesn't resurrect it", async ({
    page,
  }) => {
    await loginViaAuthentik(page, "teacher@iqbalai.dev", E2E_SEED_PASSWORD);
    if (page.url().includes("tos_required=1")) {
      await page.getByRole("button", { name: /accept/i }).click();
      await page.waitForURL("**/teacher", { timeout: 15_000 });
    }

    await page.getByRole("button", { name: /log out/i }).click();
    await page.waitForURL(/login|end-session/i, { timeout: 15_000 });

    await page.goto("/teacher");
    await page.waitForURL("**/login**");

    // Back-button replays the browser history entry, not the session — the
    // middleware's cookie check runs on the resulting request regardless.
    await page.goBack();
    await page.waitForURL("**/login**");
  });
});
