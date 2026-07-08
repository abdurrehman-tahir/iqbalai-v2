import { describe, it, expect, vi, beforeEach } from "vitest";

const fetchMock = vi.fn();

vi.stubGlobal("fetch", fetchMock);

describe("api client credentials (M-07b T-244)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ data: { ok: true } }),
    });
  });

  it("sends credentials include on auth login without Authorization header", async () => {
    const { authApi } = await import("../index");
    await authApi.login({ email: "a@b.com", password: "secret" });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.credentials).toBe("include");
    const headers = init.headers as Record<string, string>;
    expect(headers.Authorization).toBeUndefined();
  });

  it("omits Authorization when COOKIE_AUTH sentinel is passed", async () => {
    const { COOKIE_AUTH } = await import("@/lib/auth");
    const { tosApi } = await import("../index");
    await tosApi.getCurrent(COOKIE_AUTH);

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.credentials).toBe("include");
    const headers = init.headers as Record<string, string>;
    expect(headers.Authorization).toBeUndefined();
  });

  it("still sends Bearer header for legacy OIDC JWT", async () => {
    const { tosApi } = await import("../index");
    await tosApi.getCurrent("real-jwt-token");

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const headers = init.headers as Record<string, string>;
    expect(headers.Authorization).toBe("Bearer real-jwt-token");
  });
});
