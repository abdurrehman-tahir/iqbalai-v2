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

/** Authentik OIDC login URL (triggers browser redirect). */
export function getLoginUrl(): string {
  const authentikBase =
    process.env.NEXT_PUBLIC_AUTHENTIK_URL ?? "http://localhost:9000";
  const clientId =
    process.env.NEXT_PUBLIC_AUTHENTIK_CLIENT_ID ?? "iqbalai-frontend";
  const redirectUri = encodeURIComponent(
    (process.env.NEXT_PUBLIC_APP_URL ?? "http://localhost:3000") +
      "/auth/callback",
  );
  return (
    `${authentikBase}/application/o/authorize/` +
    `?client_id=${clientId}` +
    `&response_type=code` +
    `&scope=openid+profile+email` +
    `&redirect_uri=${redirectUri}`
  );
}

export function getLogoutUrl(): string {
  const authentikBase =
    process.env.NEXT_PUBLIC_AUTHENTIK_URL ?? "http://localhost:9000";
  const redirectUri = encodeURIComponent(
    (process.env.NEXT_PUBLIC_APP_URL ?? "http://localhost:3000") + "/login",
  );
  return `${authentikBase}/application/o/iqbalai-frontend/end-session/?redirect_uri=${redirectUri}`;
}
