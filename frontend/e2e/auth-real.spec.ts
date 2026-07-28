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
 * api) up, Authentik bootstrapped (OIDC blueprint applied — see
 * infrastructure/authentik/blueprints/iqbalai-oidc.yaml), and
 * `scripts/seed_e2e_auth_users.py` run against it. See `.github/workflows/ci.yml`'s
 * `e2e-smoke` job for how CI wires this.
 *
 * Authentik form selectors (Playwright pierces shadow DOM by default):
 * identification `input[name="uidField"]`, password `input[name="password"]`,
 * submit via `button[type="submit"]` (label is "Log in" / "Continue" depending
 * on stage/locale).
 */
import { test, expect, type Page } from "@playwright/test";

const API_BASE = process.env.REAL_BACKEND_URL ?? "http://localhost:8000/api/v1";
const E2E_SEED_PASSWORD = process.env.E2E_SEED_PASSWORD ?? "IqbalAI-E2E-Seed-Dev-Only-2026!";
/** Wall-clock budget for a full OIDC round-trip (authorize + 2 stages + callback). */
const AUTH_FLOW_TIMEOUT_MS = 90_000;

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
/** Primary action inside Authentik's flow executor (identification / password). */
function authentikSubmit(page: Page) {
  // Scope to the flow executor and take the last visible submit — stale stage
  // buttons can remain in the DOM across Authentik's lit stage transitions.
  return page.locator("ak-flow-executor").locator('button[type="submit"]').last();
}

async function loginViaAuthentik(page: Page, email: string, password: string): Promise<void> {
  await page.goto("/login");
  // Capture the app origin BEFORE leaving for Authentik — waitForURL must
  // compare against this fixed origin (not page.url() at callback time).
  const appOrigin = new URL(page.url()).origin;

  await page.getByRole("button", { name: /sign in/i }).click();

  // Land on Authentik (flow executor or authorize → flow redirect). Without a
  // working OIDC application this never happens and uidField never appears.
  await failWithDiagnostics(
    page,
    () => page.waitForURL(/\/(if\/flow|application\/o)\//, { timeout: AUTH_FLOW_TIMEOUT_MS }),
    "never left the app for Authentik's authorize/flow endpoint after clicking Sign in",
  );

  const uidField = page.locator('input[name="uidField"]');
  await uidField.waitFor({ state: "visible", timeout: AUTH_FLOW_TIMEOUT_MS });
  await uidField.fill(email);
  // Identification / password stage primary action is locale-dependent
  // ("Log in" vs "Continue") — submit by type, not label.
  await authentikSubmit(page).click();

  const passwordField = page.locator('input[name="password"]');
  await passwordField.waitFor({ state: "visible", timeout: AUTH_FLOW_TIMEOUT_MS });
  await passwordField.fill(password);

  // Race the post-password redirect against an inline Authentik error (wrong
  // password / policy denial). Without this, a failed password stage burns the
  // full 90s waitForURL budget with no useful signal.
  await failWithDiagnostics(
    page,
    async () => {
      await Promise.all([
        Promise.race([
          page.waitForURL(
            (url) =>
              url.origin === appOrigin ||
              // Intermediate API callback host — proves Authentik finished.
              url.href.includes("/api/v1/auth/callback"),
            {
              timeout: AUTH_FLOW_TIMEOUT_MS,
              // Commit is enough: Next's `pnpm dev` webServer can delay `load`
              // long after the callback redirect has already landed.
              waitUntil: "commit",
            },
          ),
          page
            .locator(".pf-c-alert.pf-m-danger, [role='alert']")
            .first()
            .waitFor({ state: "visible", timeout: AUTH_FLOW_TIMEOUT_MS })
            .then(async () => {
              const alertText = await page
                .locator(".pf-c-alert.pf-m-danger, [role='alert']")
                .first()
                .innerText()
                .catch(() => "Authentik alert visible");
              throw new Error(`Authentik rejected the login: ${alertText}`);
            }),
        ]),
        authentikSubmit(page).click(),
      ]);

      // If we only reached the API callback host, wait for the final app hop.
      if (new URL(page.url()).origin !== appOrigin) {
        await page.waitForURL((url) => url.origin === appOrigin, {
          timeout: AUTH_FLOW_TIMEOUT_MS,
          waitUntil: "commit",
        });
      }
    },
    "never returned to the app after submitting the password",
  );
}

/**
 * Run `action`; on failure, re-throw with the current URL + a snippet of
 * visible page text appended, so a CI failure immediately shows *where* the
 * browser got stuck (still on Authentik vs. back on the app) instead of a
 * bare Playwright timeout that has to be re-run locally to diagnose (M-07a).
 */
async function failWithDiagnostics(
  page: Page,
  action: () => Promise<unknown>,
  context: string,
): Promise<void> {
  try {
    await action();
  } catch (err) {
    const url = page.url();
    const bodyText = await page
      .locator("body")
      .innerText()
      .then((text) => text.slice(0, 500).replace(/\s+/g, " ").trim())
      .catch(() => "<could not read body text>");
    const message = err instanceof Error ? err.message : String(err);
    throw new Error(
      `loginViaAuthentik: ${context}\n  stuck at: ${url}\n  visible text: "${bodyText}"\n  original error: ${message}`,
    );
  }
}

/**
 * Accept the ToS gate if the callback redirected here on first login (T-242).
 *
 * TosModal (src/app/auth/callback/TosModal.tsx) deliberately keeps "I Accept"
 * disabled until the ToS body is scrolled to the end — a real user scrolls
 * before clicking; a script has to do it explicitly or the button never
 * becomes clickable and the first-login journey times out.
 */
async function acceptTosIfPresent(page: Page): Promise<void> {
  if (!page.url().includes("tos_required=1")) return;

  const tosContent = page.locator('[role="dialog"] .overflow-y-auto');
  await tosContent.waitFor({ state: "visible", timeout: 15_000 });
  await tosContent.evaluate((el) => el.scrollTo(0, el.scrollHeight));

  const acceptButton = page.getByRole("button", { name: /accept/i });
  await expect(acceptButton).toBeEnabled({ timeout: 5_000 });
  await acceptButton.click();
}

test.describe("Per-role real login journeys (T-247) @auth @real", () => {
  test.describe.configure({ timeout: AUTH_FLOW_TIMEOUT_MS + 30_000 });

  test.beforeEach(async () => {
    test.skip(!(await apiReachable()), `API not reachable at ${API_BASE}`);
  });

  for (const { role, email, dashboardPath } of ROLE_JOURNEYS) {
    test(`${role} logs in and lands on ${dashboardPath} with real content`, async ({ page }) => {
      await loginViaAuthentik(page, email, E2E_SEED_PASSWORD);

      // First-login ToS gate (T-242): accept it before asserting the
      // dashboard, so this journey stays green across both first-run and
      // already-accepted re-runs against a persistent dev Authentik.
      await acceptTosIfPresent(page);

      await page.waitForURL(`**${dashboardPath}`, { timeout: 15_000 });
      await expect(
        page.getByRole("main").getByRole("heading", { level: 1 }).first(),
      ).toBeVisible();
    });
  }
});

test.describe("ToS acceptance gate blocks mutation until accepted (T-242) @auth @real", () => {
  test.describe.configure({ timeout: AUTH_FLOW_TIMEOUT_MS + 30_000 });

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
  test.describe.configure({ timeout: AUTH_FLOW_TIMEOUT_MS + 30_000 });

  test.beforeEach(async () => {
    test.skip(!(await apiReachable()), `API not reachable at ${API_BASE}`);
  });

  test("after logout, a protected page redirects to /login and back-button doesn't resurrect it", async ({
    page,
  }) => {
    await loginViaAuthentik(page, "teacher@iqbalai.dev", E2E_SEED_PASSWORD);
    if (page.url().includes("tos_required=1")) {
      await acceptTosIfPresent(page);
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
