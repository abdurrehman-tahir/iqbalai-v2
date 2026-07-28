import { NextResponse, type NextRequest } from "next/server";

/**
 * Root cause (M-07a login-flow remediation): there was no middleware at all,
 * so an unauthenticated request for e.g. `/teacher` rendered the page shell
 * directly — `useClientAuth` (src/hooks/use-client-auth.ts) only returns a
 * post-hydration truthy sentinel, never a real credential, so nothing on the
 * client ever redirected either. The actual authorization decision still
 * belongs to the API (`AuthMiddleware`, api/app/core/middleware.py) — this
 * middleware is a cheap, same-origin first line of defense that keeps a
 * session-less browser from ever reaching a protected page shell, matching
 * the T-244 "unauthenticated access -> /login" contract the E2E suite
 * exercises (frontend/e2e/auth-real.spec.ts).
 *
 * Cookie name mirrors `api/app/core/cookies.py`'s `ACCESS_COOKIE`. It's
 * HttpOnly (never JS-readable) but middleware runs server-side (Edge/Node
 * runtime) and reads the raw request header, so HttpOnly doesn't block this.
 * Presence-only check — a stale/forged cookie still gets rejected by the API
 * itself (401), which then leaves the SPA in its existing error/redirect
 * handling; this layer only closes the "no cookie at all" gap.
 */
const SESSION_COOKIE = "iqbalai_access";
const PLAYWRIGHT_MOCK_BYPASS_ENV = "PLAYWRIGHT_BYPASS_AUTH_MIDDLEWARE";

/**
 * Exact-match public routes — reachable with no session at all.
 *   "/"                    marketing/landing page
 *   "/login"                the login entry point itself
 *   "/accept-invite"        invite-link landing (pre-auth by design)
 *   "/independent/signup"   independent teacher/student self-signup
 *   "/parent/signup"        parent self-signup (email-link based)
 */
const PUBLIC_EXACT_PATHS: ReadonlySet<string> = new Set([
  "/",
  "/login",
  "/accept-invite",
  "/independent/signup",
  "/parent/signup",
]);

/**
 * Path *prefixes* that are public regardless of what follows.
 *   "/auth/"  the OIDC callback + ToS-gate page (frontend/src/app/auth/callback)
 *             — reached mid-login, before any session cookie exists yet.
 */
const PUBLIC_PATH_PREFIXES: readonly string[] = ["/auth/"];

/** Exported for unit testing (src/__tests__/middleware.test.ts) without a full NextRequest. */
export function isPublicPath(pathname: string): boolean {
  if (PUBLIC_EXACT_PATHS.has(pathname)) return true;
  return PUBLIC_PATH_PREFIXES.some((prefix) => pathname.startsWith(prefix));
}

export function middleware(request: NextRequest): NextResponse {
  const { pathname } = request.nextUrl;

  if (isPublicPath(pathname)) {
    return NextResponse.next();
  }

  // Playwright's @smoke @mock suite stubs `/auth/me` and related APIs in the
  // browser without establishing a real cookie session first. Allow CI/local
  // mock runs to opt out explicitly, while keeping the real route guard active
  // for product traffic and the @auth @real suite.
  if (process.env[PLAYWRIGHT_MOCK_BYPASS_ENV] === "1") {
    return NextResponse.next();
  }

  if (request.cookies.has(SESSION_COOKIE)) {
    return NextResponse.next();
  }

  const loginUrl = new URL("/login", request.url);
  loginUrl.searchParams.set("next", `${pathname}${request.nextUrl.search}`);
  return NextResponse.redirect(loginUrl);
}

export const config = {
  // Next.js's recommended default: skip framework internals + the favicon +
  // common static-asset extensions so middleware only runs on page/document
  // navigations (locale is read from a cookie, not a URL prefix — see
  // src/i18n/request.ts — so no next-intl routing concern here).
  matcher: [
    "/((?!_next/static|_next/image|favicon\\.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico|txt|xml|json|woff2?)$).*)",
  ],
};
