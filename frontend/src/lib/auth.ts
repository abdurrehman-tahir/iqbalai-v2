/**
 * Auth helpers for the API-owned, HttpOnly-cookie OIDC session.
 */

import type { components } from "@/lib/api/schema";

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

export function getToken(): string | null {
  // Tokens are intentionally HttpOnly and never exposed to browser JavaScript.
  return null;
}

export function setToken(_token: string): void {
  // Compatibility no-op while feature callers migrate to cookie credentials.
  void _token;
}

export function clearToken(): void {
  sessionStorage.removeItem(USER_KEY);
}

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

export interface LoginUrlOptions {
  /** Force Authentik to show the login form (avoids reusing another user's SSO session). */
  promptLogin?: boolean;
  /** Pre-fill the invited user's email on the Authentik login screen. */
  loginHint?: string;
}

/** API-owned OIDC login endpoint (the API creates PKCE/state/nonce). */
export function getLoginUrl(options: LoginUrlOptions = {}): string {
  const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
  const params = new URLSearchParams();
  if (options.promptLogin) {
    // Prompt and login_hint are advisory-only until the API accepts them. They
    // must never be used to build an IdP authorize URL in the browser.
    params.set("next", "/");
  }
  return `${apiBase}/auth/login${params.size ? `?${params.toString()}` : ""}`;
}

/**
 * Every role that can log in — the school-tenant `UserRole` union plus the two
 * independent-tenant roles. Sourced from the generated OpenAPI types so the set
 * tracks the backend enum automatically (frontend-master Rule 14 [enum-switch-drift]).
 */
export type AppRole =
  | components["schemas"]["UserRole"]
  | components["schemas"]["IndependentUserRole"];

/**
 * Compile-time-exhaustive role set. `Record<AppRole, true>` forces every union
 * member to appear as a key: add a role to the backend enum (regenerate the
 * types) and this object fails `tsc` until the new role is handled here and in
 * `getPostLoginPath`. `ALL_APP_ROLES` derives its runtime list from these keys,
 * so tests never hand-enumerate roles (audit A1 root cause).
 */
const APP_ROLES: Record<AppRole, true> = {
  platform_admin: true,
  district_admin: true,
  school_admin: true,
  coordinator: true,
  teacher: true,
  student: true,
  parent: true,
  independent_teacher: true,
  independent_student: true,
};

export const ALL_APP_ROLES = Object.keys(APP_ROLES) as AppRole[];

/** True when an arbitrary string is a known application role. */
export function isAppRole(role: string): role is AppRole {
  return Object.prototype.hasOwnProperty.call(APP_ROLES, role);
}

/**
 * Coerce an untrusted role string (e.g. from a decoded JWT) to a known
 * `AppRole`, falling back to `platform_admin` for unrecognised values so a
 * malformed token never crashes routing.
 */
export function toAppRole(role: string): AppRole {
  return isAppRole(role) ? role : "platform_admin";
}

/**
 * Route a user lands on after login based on role (flow-2 §3.1).
 * Exhaustive switch over the full `AppRole` union: the `never` guard in the
 * default branch makes deleting any case (or adding an unhandled role to the
 * enum) fail `tsc` — closing audit A1 where `student`/`parent` silently fell
 * through to `/admin`.
 */
export function getPostLoginPath(role: AppRole): string {
  switch (role) {
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
    default: {
      const _exhaustive: never = role;
      return _exhaustive;
    }
  }
}

export function getLogoutUrl(): string {
  return "/logout";
}
