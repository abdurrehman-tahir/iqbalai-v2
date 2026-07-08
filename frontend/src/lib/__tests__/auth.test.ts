import { describe, it, expect, vi, beforeEach } from "vitest";
import { COOKIE_AUTH, TOKEN_KEY, USER_KEY, getAuthCredential, getUser, setUser, clearSession } from "../auth";

const MOCK_USER = {
  user_id: "u-001",
  email: "admin@iqbalai.com",
  role: "platform_admin",
  tos_acceptance_required: false,
  current_tos_version_id: "tos-v1",
};

beforeEach(() => {
  sessionStorage.clear();
});

describe("getAuthCredential (M-07b T-244)", () => {
  it("returns COOKIE_AUTH when user cache exists and no legacy JWT", () => {
    setUser(MOCK_USER);
    expect(getAuthCredential()).toBe(COOKIE_AUTH);
  });

  it("returns legacy JWT when present (oidc_redirect fallback)", () => {
    sessionStorage.setItem(TOKEN_KEY, "legacy-jwt");
    expect(getAuthCredential()).toBe("legacy-jwt");
  });

  it("returns null when logged out", () => {
    expect(getAuthCredential()).toBeNull();
  });
});

describe("clearSession", () => {
  it("clears user cache and legacy token", () => {
    sessionStorage.setItem(TOKEN_KEY, "tok");
    setUser(MOCK_USER);
    clearSession();
    expect(getUser()).toBeNull();
    expect(sessionStorage.getItem(TOKEN_KEY)).toBeNull();
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

describe("buildAppLoginUrl (M-07b)", () => {
  it("returns /login when no email is provided", async () => {
    const { buildAppLoginUrl } = await import("../auth");
    expect(buildAppLoginUrl()).toBe("/login");
  });

  it("prefills email via query param", async () => {
    const { buildAppLoginUrl } = await import("../auth");
    expect(buildAppLoginUrl("teacher@iqbalai.dev")).toBe(
      "/login?email=teacher%40iqbalai.dev",
    );
  });
});

describe("getLoginUrl — Authentik base resolution (fail-loud guard)", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("uses the configured NEXT_PUBLIC_AUTHENTIK_URL when set", async () => {
    const { getLoginUrl } = await import("../auth");
    vi.stubEnv("NEXT_PUBLIC_AUTHENTIK_URL", "https://iqbalai.com/idp");
    expect(getLoginUrl()).toContain(
      "https://iqbalai.com/idp/application/o/authorize/",
    );
  });

  it("throws in production when NEXT_PUBLIC_AUTHENTIK_URL is unset", async () => {
    const { getLoginUrl } = await import("../auth");
    vi.stubEnv("NEXT_PUBLIC_AUTHENTIK_URL", "");
    vi.stubEnv("NODE_ENV", "production");
    expect(() => getLoginUrl()).toThrow(/NEXT_PUBLIC_AUTHENTIK_URL is not set/);
  });

  it("falls back to localhost outside production for local dev", async () => {
    const { getLoginUrl } = await import("../auth");
    vi.stubEnv("NEXT_PUBLIC_AUTHENTIK_URL", "");
    vi.stubEnv("NODE_ENV", "development");
    expect(getLoginUrl()).toContain("http://localhost:9000");
  });
});

describe("getPostLoginPath", () => {
  it("routes district_admin to district schools dashboard", async () => {
    const { getPostLoginPath } = await import("../auth");
    expect(getPostLoginPath("district_admin")).toBe("/admin/district/schools");
  });

  it("routes school_admin to school dashboard", async () => {
    const { getPostLoginPath } = await import("../auth");
    expect(getPostLoginPath("school_admin")).toBe("/school/admin");
  });

  it("routes coordinator to coordinator dashboard", async () => {
    const { getPostLoginPath } = await import("../auth");
    expect(getPostLoginPath("coordinator")).toBe("/coordinator");
  });
});
