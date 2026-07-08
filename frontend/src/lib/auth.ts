/**
 * Auth helpers — cookie session (M-07b T-244) + optional client user cache.
 *
 * Primary auth is HttpOnly `iqbalai_access` / `iqbalai_refresh` cookies set by the
 * BFF login endpoint. The browser never stores JWTs for the default `bff` path.
 * `USER_KEY` caches post-login metadata (role, ids) for client routing only.
 *
 * Legacy OIDC redirect mode (`oidc_redirect`) may still store a JWT in sessionStorage
 * until that path is retired.
 */

/** Pass to API client methods to authenticate via cookie instead of Bearer header. */
export const COOKIE_AUTH = "__cookie__" as const;

/** @deprecated Kept for OIDC redirect fallback only — not used in BFF mode. */
export const TOKEN_KEY = "iqbalai_access_token";
export const USER_KEY = "iqbalai_user";

export interface StoredUser {
  user_id: string;
  email: string;
  role: string;
  district_id?: string | null;
  school_id?: string | null;
  tos_acceptance_required: boolean;
  current_tos_version_id: string | null;
}

/** Credential for API calls: real JWT (OIDC) or {@link COOKIE_AUTH} (BFF). */
export function getAuthCredential(): string | null {
  if (typeof window === "undefined") return null;
  const legacy = sessionStorage.getItem(TOKEN_KEY);
  if (legacy) return legacy;
  return getUser() ? COOKIE_AUTH : null;
}

/** @deprecated Use {@link getAuthCredential}. OIDC fallback reads sessionStorage JWT. */
export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return sessionStorage.getItem(TOKEN_KEY);
}

/** @deprecated BFF login must not store tokens — OIDC redirect fallback only. */
export function setToken(token: string): void {
  sessionStorage.setItem(TOKEN_KEY, token);
}

export function clearSession(): void {
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(USER_KEY);
}

/** @deprecated Alias for {@link clearSession}. */
export const clearToken = clearSession;

export function getUser(): StoredUser | null {
  if (typeof window === "undefined") return null;
  const raw = sessionStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as StoredUser;
  } catch {
    return null;
  }
}

export function setUser(user: StoredUser): void {
  sessionStorage.setItem(USER_KEY, JSON.stringify(user));
}

/** Revoke server session cookies and return to login (M-07b T-244). */
export async function performLogout(): Promise<void> {
  const { authApi } = await import("@/lib/api");
  try {
    await authApi.logout();
  } catch {
    // Still redirect — cookies may already be cleared server-side.
  }
  clearSession();
  const mode = process.env.NEXT_PUBLIC_AUTH_LOGIN_MODE ?? "bff";
  window.location.href = mode === "oidc_redirect" ? getLogoutUrl() : "/login";
}

export interface LoginUrlOptions {
  /** Force Authentik to show the login form (avoids reusing another user's SSO session). */
  promptLogin?: boolean;
  /** Pre-fill the invited user's email on the Authentik login screen. */
  loginHint?: string;
}

/**
 * Deploy-critical: the browser-facing Authentik base URL.
 *
 * A missing value must fail LOUD in production — silently falling back to
 * `localhost:9000` sends real users to a dev host (audit finding B1 /
 * `[env-fallback]` class). In dev/test we keep the localhost default so the
 * composed stack works out of the box. In production the value must be the
 * public `/idp` base (e.g. `https://iqbalai.com/idp`) so the authorize URL
 * routes through nginx's `/idp/` proxy (ARCH §6.15, §15.11).
 */
function resolveAuthentikBase(): string {
  const configured = process.env.NEXT_PUBLIC_AUTHENTIK_URL;
  if (configured) return configured;
  if (process.env.NODE_ENV === "production") {
    throw new Error(
      "NEXT_PUBLIC_AUTHENTIK_URL is not set. Refusing to build the login URL " +
        "against the localhost:9000 fallback in production — set it to the public " +
        "/idp base (e.g. https://iqbalai.com/idp).",
    );
  }
  return "http://localhost:9000";
}

/** Authentik OIDC login URL — `oidc_redirect` fallback only (M-07b T-245). */
export function getLoginUrl(options: LoginUrlOptions = {}): string {
  const authentikBase = resolveAuthentikBase();
  const clientId =
    process.env.NEXT_PUBLIC_AUTHENTIK_CLIENT_ID ?? "iqbalai-frontend";
  const redirectUri = encodeURIComponent(
    (process.env.NEXT_PUBLIC_APP_URL ?? "http://localhost:3000") +
      "/auth/callback",
  );
  const params = new URLSearchParams({
    client_id: clientId,
    response_type: "code",
    scope: "openid profile email",
    redirect_uri: decodeURIComponent(redirectUri),
  });
  if (options.promptLogin) {
    params.set("prompt", "login");
  }
  if (options.loginHint) {
    params.set("login_hint", options.loginHint);
  }
  return `${authentikBase}/application/o/authorize/?${params.toString()}`;
}

/** Branded in-app login URL (M-07b). Used after signup/invite instead of Authentik redirect. */
export function buildAppLoginUrl(email?: string): string {
  if (!email) return "/login";
  return `/login?email=${encodeURIComponent(email)}`;
}

/** Route a user lands on after login based on role (flow-2 §3.1). */
export function getPostLoginPath(role: string): string {
  switch (role) {
    case "district_admin":
      return "/admin/district/schools";
    case "school_admin":
      return "/school/admin";
    case "coordinator":
      return "/coordinator";
    case "teacher":
      return "/teacher";
    case "student":
      return "/student";
    case "parent":
      return "/parent";
    case "independent_teacher":
      return "/independent/teacher";
    case "independent_student":
      return "/independent/student";
    default:
      return "/admin";
  }
}

/** Authentik end-session URL — `oidc_redirect` logout fallback only. */
export function getLogoutUrl(): string {
  const authentikBase = resolveAuthentikBase();
  const redirectUri = encodeURIComponent(
    (process.env.NEXT_PUBLIC_APP_URL ?? "http://localhost:3000") + "/login",
  );
  return `${authentikBase}/application/o/iqbalai-frontend/end-session/?redirect_uri=${redirectUri}`;
}
