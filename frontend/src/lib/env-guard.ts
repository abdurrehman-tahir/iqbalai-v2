/**
 * Fail-loud guard for deploy-critical auth env vars (T-240, audit B1).
 *
 * `lib/auth.ts` falls back to localhost URLs when these are unset — a
 * necessary dev convenience, but silently shipping that fallback to
 * production redirects testers to a dev port instead of Authentik
 * (live-confirmed on staging 2026-07-13; AUDIT_LOG.md [env-fallback]).
 * Production builds must fail instead of silently defaulting.
 */

export const DEPLOY_CRITICAL_AUTH_ENV_VARS = [
  "NEXT_PUBLIC_AUTHENTIK_URL",
  "NEXT_PUBLIC_APP_URL",
  "NEXT_PUBLIC_AUTHENTIK_CLIENT_ID",
] as const;

export function assertAuthEnv(
  nodeEnv: string | undefined,
  env: Record<string, string | undefined> = process.env,
  warn: (message: string) => void = console.warn,
): void {
  const missing = DEPLOY_CRITICAL_AUTH_ENV_VARS.filter((key) => !env[key]);
  if (missing.length === 0) return;

  if (nodeEnv === "production") {
    throw new Error(
      `Missing required env var(s) for production: ${missing.join(", ")}. ` +
        "These must point at the deployed Authentik public /idp URL and app URL " +
        "(see .env.example) — a production build must never fall back to localhost.",
    );
  }

  warn(
    `[env-guard] Missing ${missing.join(", ")} — falling back to localhost defaults for local dev. ` +
      "Set these before deploying (see .env.example).",
  );
}
