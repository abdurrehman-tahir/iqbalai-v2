import { describe, it, expect, beforeEach } from "vitest";
import {
  ALL_APP_ROLES,
  TOKEN_KEY,
  USER_KEY,
  getToken,
  setToken,
  clearToken,
  getUser,
  setUser,
  getLoginUrl,
  getPostLoginPath,
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
  it("never exposes an HttpOnly cookie token to JavaScript", () => {
    expect(getToken()).toBeNull();
    sessionStorage.setItem(TOKEN_KEY, "my-jwt");
    expect(getToken()).toBeNull();
  });
});

describe("setToken / clearToken", () => {
  it("does not persist a token and clears only display state", () => {
    setToken("abc.def.ghi");
    expect(sessionStorage.getItem(TOKEN_KEY)).toBeNull();

    setUser(MOCK_USER);
    clearToken();
    expect(getToken()).toBeNull();
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
  it("targets the API-owned OIDC entry point", () => {
    const url = getLoginUrl({
      promptLogin: true,
      loginHint: "district@school.edu",
    });
    expect(url).toContain("/api/v1/auth/login");
    expect(url).not.toContain("authorize");
    expect(url).not.toContain("login_hint");
  });
});

describe("getPostLoginPath", () => {
  const expectedPaths = {
    platform_admin: "/admin",
    district_admin: "/admin/district/schools",
    school_admin: "/school/admin",
    coordinator: "/coordinator",
    teacher: "/teacher",
    student: "/student",
    parent: "/parent",
    independent_teacher: "/independent/teacher",
    independent_student: "/independent/student",
  } as const;

  it("maps every generated application role to its dashboard", () => {
    expect(ALL_APP_ROLES).toEqual(Object.keys(expectedPaths));
    for (const role of ALL_APP_ROLES) {
      expect(getPostLoginPath(role)).toBe(expectedPaths[role]);
    }
  });
});
