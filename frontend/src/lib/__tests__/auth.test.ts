import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, it, expect } from "vitest";
import { getLoginRedirectUrl, getPostLoginPath, ALL_ROLES, type Role } from "../auth";

describe("no sessionStorage token usage (T-245, ARCH §6.4/§6.17)", () => {
  it("lib/auth.ts never reads or writes sessionStorage", () => {
    const thisFile = fileURLToPath(import.meta.url);
    const authTsPath = join(dirname(thisFile), "..", "auth.ts");
    const source = readFileSync(authTsPath, "utf-8");
    expect(source).not.toMatch(/sessionStorage/);
  });
});

describe("getLoginRedirectUrl", () => {
  it("points at the API's own /auth/login, not Authentik directly (T-245, ARCH §6.4)", () => {
    const url = getLoginRedirectUrl();
    expect(url).toContain("/auth/login");
    expect(url).not.toContain("authentik");
  });

  it("adds prompt_login and login_hint for post-invite sign-in", () => {
    const url = getLoginRedirectUrl({
      promptLogin: true,
      loginHint: "district@school.edu",
    });
    expect(url).toContain("prompt_login=true");
    expect(url).toContain("login_hint=district%40school.edu");
  });

  it("adds next when provided", () => {
    const url = getLoginRedirectUrl({ next: "/coordinator/grades" });
    expect(url).toContain("next=%2Fcoordinator%2Fgrades");
  });

  it("omits optional params when not requested", () => {
    const url = getLoginRedirectUrl();
    expect(url).not.toContain("prompt_login");
    expect(url).not.toContain("login_hint");
    expect(url).not.toContain("next=");
  });
});

// T-239: expected paths keyed by `Role` — TS enforces every ALL_ROLES member has
// an entry here (missing/extra keys fail to typecheck), so this table can't drift
// out of sync with the role union the way the old hand-listed test cases did.
const EXPECTED_DASHBOARD: Record<Role, string> = {
  platform_admin: "/admin",
  district_admin: "/admin/district/schools",
  school_admin: "/school/admin",
  coordinator: "/coordinator",
  teacher: "/teacher",
  student: "/student",
  parent: "/parent",
  independent_teacher: "/independent/teacher",
  independent_student: "/independent/student",
};

describe("getPostLoginPath", () => {
  it("covers every role in the union", () => {
    expect(ALL_ROLES).toHaveLength(9);
  });

  it.each(ALL_ROLES)("routes %s to its documented dashboard", (role) => {
    expect(getPostLoginPath(role)).toBe(EXPECTED_DASHBOARD[role]);
  });

  it("throws for an unrecognized role instead of silently falling through", () => {
    expect(() => getPostLoginPath("not_a_real_role")).toThrow(/unhandled role/i);
  });
});
