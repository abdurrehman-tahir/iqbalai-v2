/**
 * Typed API client for the IqbalAI FastAPI backend.
 * All fetch calls go through here — never use raw fetch() in components.
 */

import type {
  DisclaimerVersionRead,
  ExamSyllabusCreate,
  ExamSyllabusRead,
  ExamSyllabusUpdate,
  Notification,
  PersonaRead,
  PersonaUpdate,
  PostLoginResponse,
  SubscriptionTierCreate,
  SubscriptionTierRead,
  SubscriptionTierUpdate,
  TosAcceptResponse,
  TosDeclineResponse,
  TosVersion,
  TosVersionRead,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export type {
  AuditEntry,
  Notification,
  PersonaRead as Persona,
  ExamSyllabusRead as Syllabus,
  SubscriptionTierRead as SubscriptionTier,
  LibraryBookRead as LibraryBook,
  TosVersion,
} from "./types";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type ValidationDetail = {
  loc?: unknown[];
  msg?: string;
  type?: string;
};

function formatValidationDetail(detail: ValidationDetail): string {
  const path = Array.isArray(detail.loc)
    ? detail.loc.filter((part) => part !== "body").join(".")
    : "";
  const msg = detail.msg ?? "Validation error";
  return path ? `${path}: ${msg}` : msg;
}

function parseApiErrorBody(
  body: unknown,
  status: number,
): { code: string; message: string; details?: unknown } {
  if (body && typeof body === "object") {
    const record = body as Record<string, unknown>;

    if (record.error && typeof record.error === "object") {
      const err = record.error as Record<string, unknown>;
      return {
        code: String(err.code ?? "UNKNOWN_ERROR"),
        message: String(err.message ?? `Request failed with status ${status}`),
        details: err.details,
      };
    }

    if (Array.isArray(record.detail)) {
      const details = record.detail as ValidationDetail[];
      return {
        code: "VALIDATION_ERROR",
        message: details.map(formatValidationDetail).join("; "),
        details,
      };
    }

    if (typeof record.code === "string") {
      return {
        code: record.code,
        message: String(record.message ?? `Request failed with status ${status}`),
        details: record.details,
      };
    }
  }

  return {
    code: "UNKNOWN_ERROR",
    message: `Request failed with status ${status}`,
  };
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  token?: string,
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> | undefined),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (!res.ok) {
    let body: unknown = {};
    try {
      body = await res.json();
    } catch {
      // ignore parse errors
    }
    const parsed = parseApiErrorBody(body, res.status);
    throw new ApiError(res.status, parsed.code, parsed.message, parsed.details);
  }

  if (res.status === 204) return undefined as T;

  const envelope = await res.json();
  return (envelope.data ?? envelope) as T;
}

function mapTosVersion(raw: TosVersionRead): TosVersion {
  return {
    id: raw.id,
    version: raw.version_number,
    content: raw.content_md,
    effective_at: raw.effective_at,
  };
}

function mapDisclaimer(raw: DisclaimerVersionRead): TosVersion {
  return {
    id: raw.id,
    version: raw.version_number,
    content: raw.content,
    effective_at: raw.effective_at,
  };
}

// ── Auth ──────────────────────────────────────────────────────────────────────

export const authApi = {
  postLogin: (token: string) =>
    request<PostLoginResponse>("/auth/post-login", { method: "POST" }, token),
};

// ── ToS ───────────────────────────────────────────────────────────────────────

export const tosApi = {
  getCurrent: async (token: string) =>
    mapTosVersion(await request<TosVersionRead>("/tos/current", {}, token)),
  acceptTos: (token: string, tosVersionId: string) =>
    request<TosAcceptResponse>(
      "/users/me/accept-tos",
      { method: "POST", body: JSON.stringify({ tos_version_id: tosVersionId }) },
      token,
    ),
  declineTos: (token: string) =>
    request<TosDeclineResponse>(
      "/users/me/decline-tos",
      { method: "POST", body: JSON.stringify({}) },
      token,
    ),
  list: async (token: string) =>
    (await request<TosVersionRead[]>("/admin/tos", {}, token)).map(mapTosVersion),
  publish: async (token: string, content: string) => {
    const raw = await request<TosVersionRead>(
      "/admin/tos",
      { method: "POST", body: JSON.stringify({ content_md: content }) },
      token,
    );
    return { id: raw.id, version: raw.version_number };
  },
  listDisclaimer: async (token: string) =>
    (await request<DisclaimerVersionRead[]>("/admin/disclaimer", {}, token)).map(
      mapDisclaimer,
    ),
  publishDisclaimer: async (token: string, content: string) => {
    const raw = await request<DisclaimerVersionRead>(
      "/admin/disclaimer",
      { method: "POST", body: JSON.stringify({ content }) },
      token,
    );
    return { id: raw.id, version: raw.version_number };
  },
};

// ── Exam Syllabi ──────────────────────────────────────────────────────────────

export const syllabiApi = {
  list: (token: string) =>
    request<ExamSyllabusRead[]>("/admin/exam-syllabi", {}, token),
  create: (token: string, data: ExamSyllabusCreate) =>
    request<ExamSyllabusRead>(
      "/admin/exam-syllabi",
      { method: "POST", body: JSON.stringify(data) },
      token,
    ),
  update: (token: string, id: string, data: ExamSyllabusUpdate) =>
    request<ExamSyllabusRead>(
      `/admin/exam-syllabi/${id}`,
      { method: "PUT", body: JSON.stringify(data) },
      token,
    ),
  delete: (token: string, id: string) =>
    request<void>(`/admin/exam-syllabi/${id}`, { method: "DELETE" }, token),
};

// ── Personas ──────────────────────────────────────────────────────────────────

export const personasApi = {
  list: (token: string) =>
    request<PersonaRead[]>("/admin/personas", {}, token),
  update: (token: string, id: string, data: PersonaUpdate) =>
    request<PersonaRead>(
      `/admin/personas/${id}`,
      { method: "PUT", body: JSON.stringify(data) },
      token,
    ),
};

// ── Subscription Tiers ────────────────────────────────────────────────────────

export const subscriptionsApi = {
  list: (token: string) =>
    request<SubscriptionTierRead[]>("/admin/subscription-tiers", {}, token),
  create: (token: string, data: SubscriptionTierCreate) =>
    request<SubscriptionTierRead>(
      "/admin/subscription-tiers",
      { method: "POST", body: JSON.stringify(data) },
      token,
    ),
  update: (token: string, id: string, data: SubscriptionTierUpdate) =>
    request<SubscriptionTierRead>(
      `/admin/subscription-tiers/${id}`,
      { method: "PUT", body: JSON.stringify(data) },
      token,
    ),
  delete: (token: string, id: string) =>
    request<void>(`/admin/subscription-tiers/${id}`, { method: "DELETE" }, token),
};

// ── Library ───────────────────────────────────────────────────────────────────

export const libraryApi = {
  list: async (token: string) => {
    const page = await request<import("./types").LibraryBookListResponse>(
      "/admin/library",
      {},
      token,
    );
    return page.items;
  },
  softDelete: (token: string, id: string) =>
    request<void>(`/admin/library/${id}`, { method: "DELETE" }, token),
};

// ── Audit Log ─────────────────────────────────────────────────────────────────

export const auditApi = {
  list: async (token: string, params?: { actor?: string; action?: string }) => {
    const qs = params
      ? "?" + new URLSearchParams(params as Record<string, string>).toString()
      : "";
    const page = await request<import("./types").AuditLogListResponse>(
      `/admin/audit-log${qs}`,
      {},
      token,
    );
    return page.items;
  },
};

// ── Notifications ─────────────────────────────────────────────────────────────

export const notificationsApi = {
  list: async (token: string): Promise<Notification[]> => {
    const res = await request<{
      items: Notification[];
      total: number;
      unread_count: number;
    }>("/notifications", {}, token);
    return res.items;
  },
  markRead: (token: string, id: string) =>
    request<void>(`/notifications/${id}/read`, { method: "POST" }, token),
};
