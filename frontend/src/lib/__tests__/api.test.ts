import { describe, it, expect, vi, beforeEach } from "vitest";
import { notificationsApi, tosApi, ApiError } from "../api/index";

// Helper: build a fake fetch that returns the given body with status 200.
function mockFetch(body: unknown, status = 200) {
  return vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  });
}

beforeEach(() => {
  vi.restoreAllMocks();
});

// ── Envelope unwrapping ───────────────────────────────────────────────────────

describe("envelope unwrapping", () => {
  it("unwraps { success, data } envelope", async () => {
    global.fetch = mockFetch({ success: true, data: { items: [], total: 0, unread_count: 0 } });
    const result = await notificationsApi.list("tok");
    expect(Array.isArray(result)).toBe(true);
  });

  it("falls back to raw body when no envelope wrapper present", async () => {
    // tosApi.getCurrent returns a plain TosVersionRead (no wrapper in some paths)
    global.fetch = mockFetch({
      id: "tos-1",
      version_number: 1,
      content_md: "# ToS",
      language: "en",
      effective_at: "2026-01-01T00:00:00Z",
    });
    const tos = await tosApi.getCurrent("tok");
    expect(tos.id).toBe("tos-1");
    expect(tos.version).toBe(1);
  });

  it("throws ApiError on non-2xx response", async () => {
    global.fetch = mockFetch(
      { code: "NOT_FOUND", message: "Resource not found" },
      404,
    );
    await expect(tosApi.getCurrent("tok")).rejects.toBeInstanceOf(ApiError);
  });

  it("ApiError carries status and code", async () => {
    global.fetch = mockFetch({ code: "FORBIDDEN", message: "Access denied" }, 403);
    try {
      await tosApi.getCurrent("tok");
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError);
      const apiErr = err as ApiError;
      expect(apiErr.status).toBe(403);
      expect(apiErr.code).toBe("FORBIDDEN");
    }
  });
});

// ── notificationsApi ──────────────────────────────────────────────────────────

describe("notificationsApi.list", () => {
  it("extracts items array from paginated response", async () => {
    const items = [
      { id: "n1", feature_namespace: "tos", title: "New ToS", body: "Please accept.", is_read: false, created_at: "2026-06-01T00:00:00Z" },
      { id: "n2", feature_namespace: "system", title: "Welcome", body: "Hi!", is_read: true, created_at: "2026-06-01T00:00:00Z" },
    ];
    global.fetch = mockFetch({ success: true, data: { items, total: 2, unread_count: 1 } });

    const result = await notificationsApi.list("tok");
    expect(result).toHaveLength(2);
    expect(result[0].id).toBe("n1");
    expect(result[1].is_read).toBe(true);
  });

  it("returns empty array when items is empty", async () => {
    global.fetch = mockFetch({ success: true, data: { items: [], total: 0, unread_count: 0 } });
    const result = await notificationsApi.list("tok");
    expect(result).toEqual([]);
  });

  it("result supports .filter() — the original crash case", async () => {
    global.fetch = mockFetch({ success: true, data: { items: [
      { id: "n1", feature_namespace: "tos", title: "T", body: "B", is_read: false, created_at: "" },
    ], total: 1, unread_count: 1 } });
    const result = await notificationsApi.list("tok");
    // This is the exact call that crashed before the fix
    expect(() => result.filter((n) => !n.is_read)).not.toThrow();
    expect(result.filter((n) => !n.is_read)).toHaveLength(1);
  });
});

// ── tosApi ────────────────────────────────────────────────────────────────────

describe("tosApi.listDisclaimer", () => {
  it("maps version_number to version — the original bug", async () => {
    global.fetch = mockFetch({
      success: true,
      data: [
        { id: "d1", version_number: 2, content: "Disclaimer v2", language: "en", effective_at: "2026-06-01T00:00:00Z" },
        { id: "d0", version_number: 1, content: "Disclaimer v1", language: "en", effective_at: "2026-01-01T00:00:00Z" },
      ],
    });
    const result = await tosApi.listDisclaimer("tok");
    expect(result[0].version).toBe(2);
    expect(result[1].version).toBe(1);
    // Ensure version is never undefined
    result.forEach((d) => expect(d.version).toBeDefined());
  });

  it("returns empty array when no disclaimers exist", async () => {
    global.fetch = mockFetch({ success: true, data: [] });
    const result = await tosApi.listDisclaimer("tok");
    expect(result).toEqual([]);
  });
});

describe("tosApi.list", () => {
  it("maps version_number to version and content_md to content", async () => {
    global.fetch = mockFetch({
      success: true,
      data: [
        { id: "t1", version_number: 3, content_md: "# ToS v3", language: "en", effective_at: "2026-06-01T00:00:00Z" },
      ],
    });
    const result = await tosApi.list("tok");
    expect(result[0].version).toBe(3);
    expect(result[0].content).toBe("# ToS v3");
  });
});
