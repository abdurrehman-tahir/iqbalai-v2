import { describe, it, expect, beforeEach } from "vitest";
import {
  TOKEN_KEY,
  USER_KEY,
  getToken,
  setToken,
  clearToken,
  getUser,
  setUser,
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

describe("getPostLoginPath", () => {
  it("routes district_admin to district schools dashboard", () => {
    expect(getPostLoginPath("district_admin")).toBe("/admin/district/schools");
  });

  it("routes school_admin to school dashboard", () => {
    expect(getPostLoginPath("school_admin")).toBe("/school/admin");
  });

  it("routes coordinator to coordinator dashboard", () => {
    expect(getPostLoginPath("coordinator")).toBe("/coordinator");
  });

  it("routes teacher to teacher dashboard", () => {
    expect(getPostLoginPath("teacher")).toBe("/teacher");
  });

  it("routes platform_admin to platform admin home", () => {
    expect(getPostLoginPath("platform_admin")).toBe("/admin");
  });
});
