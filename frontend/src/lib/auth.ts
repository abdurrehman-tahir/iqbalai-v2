/**
 * Auth helpers — role routing + login/logout redirect URLs.
 *
 * T-245: the session lives entirely in HttpOnly cookies the browser attaches
 * automatically (ARCH §6.4/§6.17). There is no JS-readable token or user
 * object here anymore — for "who am I" (display name/role in a shell, an
 * ownership check), fetch `GET /api/v1/auth/me` via `authApi.me()` /
 * `useCurrentUser()`, don't reach for browser-local storage.
 */

import { API_BASE } from "@/lib/api";
import type { IndependentUserRole, UserRole } from "@/lib/api/types";

export interface LoginRedirectOptions {
  /** Force Authentik to show the login form (avoids reusing another user's SSO session). */
  promptLogin?: boolean;
  /** Pre-fill the invited/signed-up user's email on the Authentik login screen. */
  loginHint?: string;
  /** Relative path to land on after a successful login (validated server-side). */
  next?: string;
}

/**
 * API-owned OIDC login redirect (ARCH §6.4 step 1). The API generates
 * state/nonce/PKCE and redirects on to Authentik itself — the browser's only
 * job is navigating here, never building the authorize URL or touching a
 * code/token directly.
 */
export function getLoginRedirectUrl(options: LoginRedirectOptions = {}): string {
  const params = new URLSearchParams();
  if (options.promptLogin) {
    params.set("prompt_login", "true");
  }
  if (options.loginHint) {
    params.set("login_hint", options.loginHint);
  }
  if (options.next) {
    params.set("next", options.next);
  }
  const query = params.toString();
  return `${API_BASE}/auth/login${query ? `?${query}` : ""}`;
}

/** Every role a JWT `role` claim can carry — school tenant + independent tenant. */
export type Role = UserRole | IndependentUserRole;

/**
 * Complete, ordered list of `Role` members — the single source of truth both
 * `getPostLoginPath` and its test derive their case coverage from (T-239: the
 * prior switch and its test each hand-listed roles independently, so `student`/
 * `parent` silently fell through in both without either catching the other).
 */
export const ALL_ROLES = [
  "platform_admin",
  "district_admin",
  "school_admin",
  "coordinator",
  "teacher",
  "student",
  "parent",
  "independent_teacher",
  "independent_student",
] as const satisfies readonly Role[];

// Compile-time completeness check: if `Role` (driven by the generated OpenAPI
// schema) ever gains a member missing from ALL_ROLES, this line fails to
// typecheck (`Role` would no longer be assignable to `(typeof ALL_ROLES)[number]`).
type _AllRolesCovered = Role extends (typeof ALL_ROLES)[number] ? true : never;
const _allRolesCovered: _AllRolesCovered = true;
void _allRolesCovered;

function assertNeverRole(role: never): never {
  throw new Error(`getPostLoginPath: unhandled role "${String(role)}"`);
}

/** Route a user lands on after login based on role (flow-2 §3.1). */
export function getPostLoginPath(role: string): string {
  const typedRole = role as Role;
  switch (typedRole) {
    case "platform_admin":
      return "/admin";
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
      return assertNeverRole(typedRole);
  }
}

export function getLogoutUrl(): string {
  const authentikBase =
    process.env.NEXT_PUBLIC_AUTHENTIK_URL ?? "http://localhost:9000";
  const redirectUri = encodeURIComponent(
    (process.env.NEXT_PUBLIC_APP_URL ?? "http://localhost:3000") + "/login",
  );
  return `${authentikBase}/application/o/iqbalai-frontend/end-session/?redirect_uri=${redirectUri}`;
}
