/**
 * Auth helpers — token storage and retrieval.
 * The frontend stores the Authentik JWT in sessionStorage after OIDC callback.
 */

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
  if (typeof window === "undefined") return null;
  return sessionStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  sessionStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  sessionStorage.removeItem(TOKEN_KEY);
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

/** Authentik OIDC login URL (triggers browser redirect). */
export function getLoginUrl(options: LoginUrlOptions = {}): string {
  const authentikBase =
    process.env.NEXT_PUBLIC_AUTHENTIK_URL ?? "http://localhost:9000";
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
    case "independent_teacher":
      return "/independent/teacher";
    case "independent_student":
      return "/independent/student";
    default:
      return "/admin";
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
