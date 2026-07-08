/**
 * E2E helpers for BFF custom login (M-07b T-246).
 */

import type { Page, Route } from "@playwright/test";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
const AUTHENTIK_BASE = process.env.NEXT_PUBLIC_AUTHENTIK_URL ?? "http://localhost:9000";

function envelope<T>(data: T, message = "ok") {
  return JSON.stringify({ data, message });
}

export interface BffLoginUser {
  user_id: string;
  email: string;
  role: string;
  tenant_type?: string;
  district_id?: string | null;
  school_id?: string | null;
  is_first_login?: boolean;
  tos_acceptance_required?: boolean;
  current_tos_version_id?: string | null;
  account_status?: string;
}

const DEFAULT_ADMIN: BffLoginUser = {
  user_id: "admin-1",
  email: "admin@iqbalai.dev",
  role: "platform_admin",
  tenant_type: "school",
  is_first_login: false,
  tos_acceptance_required: false,
  current_tos_version_id: null,
  account_status: "active",
};

const DEFAULT_TEACHER: BffLoginUser = {
  user_id: "teacher-1",
  email: "teacher@iqbalai.dev",
  role: "teacher",
  tenant_type: "school",
  school_id: "school-1",
  is_first_login: false,
  tos_acceptance_required: false,
  current_tos_version_id: null,
  account_status: "active",
};

/** Block navigation to Authentik hosted UI — BFF mode must never redirect there. */
export async function blockAuthentikUi(page: Page) {
  await page.route(`${AUTHENTIK_BASE}/**`, (route) =>
    route.abort("failed"),
  );
}

/** Mock POST /auth/login and subsequent cookie-authenticated API calls. */
export async function installBffLoginMocks(
  page: Page,
  loginUser: BffLoginUser = DEFAULT_ADMIN,
) {
  const accessCookie = `dev-access-${loginUser.user_id}`;

  await page.route(`${API_BASE}/auth/login`, async (route: Route) => {
    if (route.request().method() !== "POST") {
      await route.continue();
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      headers: {
        "Set-Cookie": `iqbalai_access=${accessCookie}; Path=/; HttpOnly; SameSite=Lax`,
      },
      body: envelope(loginUser),
    });
  });

  await page.route(`${API_BASE}/**`, async (route: Route) => {
    const req = route.request();
    if (req.url().includes("/auth/login")) {
      await route.continue();
      return;
    }
    const cookie = req.headers()["cookie"] ?? "";
    const hasSession =
      cookie.includes("iqbalai_access=") ||
      (req.headers()["authorization"] ?? "").startsWith("Bearer ");
    if (!hasSession && !req.url().includes("/auth/forgot-password")) {
      await route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({
          error: { code: "AUTHENTICATION_REQUIRED", message: "Authentication required" },
        }),
      });
      return;
    }
    await route.continue();
  });
}

export async function loginViaForm(
  page: Page,
  email: string,
  password: string,
) {
  await page.goto("/login");
  await page.getByLabel(/email/i).fill(email);
  await page.getByLabel(/^password$/i).fill(password);
  await page.getByRole("button", { name: /sign in/i }).click();
}

export { DEFAULT_ADMIN, DEFAULT_TEACHER, envelope, API_BASE };
