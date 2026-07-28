import { describe, it, expect } from "vitest";
import { NextRequest } from "next/server";

import { middleware, isPublicPath } from "../middleware";

function requestFor(pathname: string, cookie?: string): NextRequest {
  return new NextRequest(new URL(pathname, "http://localhost:3000"), {
    headers: cookie ? { cookie } : undefined,
  });
}

describe("isPublicPath", () => {
  it.each([
    "/",
    "/login",
    "/accept-invite",
    "/independent/signup",
    "/parent/signup",
    "/auth/callback",
  ])("treats %s as public", (path) => {
    expect(isPublicPath(path)).toBe(true);
  });

  it.each(["/teacher", "/admin", "/student/exam-frameworks", "/independent/teacher"])(
    "treats %s as protected",
    (path) => {
      expect(isPublicPath(path)).toBe(false);
    },
  );
});

describe("middleware", () => {
  it("lets a public path through with no session cookie", () => {
    const res = middleware(requestFor("/login"));
    expect(res.headers.get("location")).toBeNull();
  });

  it("redirects a protected path to /login when the session cookie is missing (T-244)", () => {
    const res = middleware(requestFor("/teacher"));
    expect(res.status).toBe(307);
    const location = res.headers.get("location");
    expect(location).toContain("/login");
    expect(location).toContain("next=%2Fteacher");
  });

  it("lets a protected path through when the iqbalai_access cookie is present", () => {
    const res = middleware(requestFor("/teacher", "iqbalai_access=some-jwt-value"));
    expect(res.headers.get("location")).toBeNull();
  });

  it("redirects /auth/callback's sibling protected routes but not /auth/callback itself", () => {
    expect(middleware(requestFor("/auth/callback")).headers.get("location")).toBeNull();
    expect(middleware(requestFor("/admin")).status).toBe(307);
  });
});
