/**
 * Typed API client for the IqbalAI FastAPI backend.
 * All fetch calls go through here — never use raw fetch() in components.
 */

import type {
  AuditEntry,
  DisclaimerVersionRead,
  ExamSyllabusRead,
  Notification,
  PersonaRead,
  PostLoginResponse,
  SubscriptionTierRead,
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
    let body: { code?: string; message?: string; details?: unknown } = {};
    try {
      body = await res.json();
    } catch {
      // ignore parse errors
    }
    throw new ApiError(
      res.status,
      body.code ?? "UNKNOWN_ERROR",
      body.message ?? `Request failed with status ${res.status}`,
      body.details,
    );
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
  create: (token: string, data: { name: string; description?: string }) =>
    request<ExamSyllabusRead>(
      "/admin/exam-syllabi",
      { method: "POST", body: JSON.stringify(data) },
      token,
    ),
  update: (token: string, id: string, data: Partial<ExamSyllabusRead>) =>
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
  update: (
    token: string,
    id: string,
    data: { system_prompt?: string; description?: string; is_active?: boolean },
  ) =>
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
  create: (token: string, data: Omit<SubscriptionTierRead, "id">) =>
    request<SubscriptionTierRead>(
      "/admin/subscription-tiers",
      { method: "POST", body: JSON.stringify(data) },
      token,
    ),
  update: (token: string, id: string, data: Partial<SubscriptionTierRead>) =>
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
  list: (token: string) =>
    request<import("./types").LibraryBookRead[]>("/admin/library", {}, token),
  softDelete: (token: string, id: string) =>
    request<void>(`/admin/library/${id}`, { method: "DELETE" }, token),
};

// ── Audit Log ─────────────────────────────────────────────────────────────────

export const auditApi = {
  list: (token: string, params?: { actor?: string; action?: string }) => {
    const qs = params
      ? "?" + new URLSearchParams(params as Record<string, string>).toString()
      : "";
    return request<AuditEntry[]>(`/admin/audit-log${qs}`, {}, token);
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
