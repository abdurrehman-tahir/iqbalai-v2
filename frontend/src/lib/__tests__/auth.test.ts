import { describe, it, expect, beforeEach } from "vitest";
import {
  TOKEN_KEY,
  USER_KEY,
  getToken,
  setToken,
  clearToken,
  getUser,
  setUser,
  getLoginUrl,
  getPostLoginPath,
  ALL_ROLES,
  type Role,
  type StoredUser,
} from "../auth";

const MOCK_USER: StoredUser = {
  user_id: "u-001",
  email: "admin@iqbalai.com",
  role: "platform_admin",
  tos_acceptance_required: false,
  current_tos_version_id: "tos-v1",
};

beforeEach(() => {
  sessionStorage.clear();
});

describe("getToken", () => {
  it("returns null when no token is stored", () => {
    expect(getToken()).toBeNull();
  });

  it("returns the stored token", () => {
    sessionStorage.setItem(TOKEN_KEY, "my-jwt");
    expect(getToken()).toBe("my-jwt");
  });
});

describe("setToken / clearToken", () => {
  it("stores and then clears the token", () => {
    setToken("abc.def.ghi");
    expect(getToken()).toBe("abc.def.ghi");

    clearToken();
    expect(getToken()).toBeNull();
  });

  it("clearToken also removes the stored user", () => {
    setToken("tok");
    setUser(MOCK_USER);
    clearToken();
    expect(getUser()).toBeNull();
  });
});

describe("getUser / setUser", () => {
  it("returns null when nothing stored", () => {
    expect(getUser()).toBeNull();
  });

  it("round-trips a user object through sessionStorage", () => {
    setUser(MOCK_USER);
    expect(getUser()).toEqual(MOCK_USER);
  });

  it("returns null when sessionStorage contains malformed JSON", () => {
    sessionStorage.setItem(USER_KEY, "{bad json");
    expect(getUser()).toBeNull();
  });
});

describe("getLoginUrl", () => {
  it("adds prompt=login and login_hint for post-invite sign-in", () => {
    const url = getLoginUrl({
      promptLogin: true,
      loginHint: "district@school.edu",
    });
    expect(url).toContain("prompt=login");
    expect(url).toContain("login_hint=district%40school.edu");
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
