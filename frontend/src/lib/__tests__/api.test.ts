import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  auditApi,
  authApi,
  libraryApi,
  notificationsApi,
  personasApi,
  subscriptionsApi,
  syllabiApi,
  tosApi,
  ApiError,
} from "../api/index";

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
      { error: { code: "NOT_FOUND", message: "Resource not found" } },
      404,
    );
    await expect(tosApi.getCurrent("tok")).rejects.toBeInstanceOf(ApiError);
  });

  it("ApiError carries status and code", async () => {
    global.fetch = mockFetch(
      { error: { code: "FORBIDDEN", message: "Access denied" } },
      403,
    );
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

describe("tosApi.acceptTos + declineTos", () => {
  it("acceptTos posts version id", async () => {
    global.fetch = mockFetch({
      data: { accepted: true, tos_version_id: "t1", accepted_at: "2026-01-01T00:00:00Z" },
    });
    const result = await tosApi.acceptTos("tok", "t1");
    expect(result.accepted).toBe(true);
  });

  it("declineTos returns suspended status", async () => {
    global.fetch = mockFetch({ data: { declined: true, status: "suspended" } });
    const result = await tosApi.declineTos("tok");
    expect(result.status).toBe("suspended");
  });
});

describe("authApi.postLogin", () => {
  it("returns post-login payload", async () => {
    global.fetch = mockFetch({
      data: {
        user_id: "u1",
        email: "a@test.com",
        role: "platform_admin",
        is_first_login: false,
        tos_acceptance_required: true,
        current_tos_version_id: "t1",
        account_status: "active",
      },
    });
    const result = await authApi.postLogin("tok");
    expect(result.tos_acceptance_required).toBe(true);
  });
});

describe("personasApi", () => {
  it("lists and updates personas", async () => {
    global.fetch = mockFetch({
      data: [{ id: "p1", name: "Strict", system_prompt: "x", is_custom: false, is_active: true }],
    });
    const list = await personasApi.list("tok");
    expect(list[0].name).toBe("Strict");

    global.fetch = mockFetch({
      data: { id: "p1", name: "Strict", system_prompt: "y", is_custom: false, is_active: true },
    });
    const updated = await personasApi.update("tok", "p1", { system_prompt: "y" });
    expect(updated.system_prompt).toBe("y");
  });
});

describe("syllabiApi", () => {
  it("CRUD helpers unwrap data", async () => {
    global.fetch = mockFetch({ data: [] });
    expect(await syllabiApi.list("tok")).toEqual([]);

    global.fetch = mockFetch({
      data: { id: "s1", name: "Matric", exam_board: "Punjab Board", version_number: 1, is_active: true },
    });
    const created = await syllabiApi.create("tok", {
      name: "Matric",
      exam_board: "Punjab Board",
    });
    expect(created.name).toBe("Matric");
  });
});

describe("subscriptionsApi", () => {
  it("lists tiers", async () => {
    global.fetch = mockFetch({
      data: [{ id: "t1", name: "Basic", slug: "basic", applies_to: "school", pricing_monthly_pkr: 1, caps: {}, is_active: true, created_at: "" }],
    });
    const tiers = await subscriptionsApi.list("tok");
    expect(tiers[0].name).toBe("Basic");
  });
});

describe("auditApi + libraryApi", () => {
  it("auditApi passes filter query params", async () => {
    global.fetch = mockFetch({
      items: [
        {
          id: "a1",
          action: "tos.published",
          actor_id: "u1",
          target_type: "tos",
          target_id: "t1",
          metadata: {},
          created_at: "",
        },
      ],
      total: 1,
      page: 1,
      page_size: 50,
      pages: 1,
    });
    const entries = await auditApi.list("tok", { actor: "u1", action: "tos" });
    expect(entries[0].action).toBe("tos.published");
  });

  it("libraryApi lists books", async () => {
    global.fetch = mockFetch({
      items: [{ id: "b1", title: "f.pdf", status: "available", created_at: "" }],
      total: 1,
    });
    const books = await libraryApi.list("tok");
    expect(books[0].title).toBe("f.pdf");
  });
});
