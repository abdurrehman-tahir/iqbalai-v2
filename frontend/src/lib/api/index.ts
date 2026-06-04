/**
 * Typed API client for the IqbalAI FastAPI backend.
 * All fetch calls go through here — never use raw fetch() in components.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

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
  // All our endpoints wrap responses in { success: true, data: ... }
  return (envelope.data ?? envelope) as T;
}

// ── Auth ──────────────────────────────────────────────────────────────────────

export const authApi = {
  postLogin: (token: string) =>
    request<{
      user_id: string;
      email: string;
      role: string;
      is_first_login: boolean;
      tos_acceptance_required: boolean;
      current_tos_version_id: string | null;
    }>("/auth/post-login", { method: "POST" }, token),
};

// ── ToS ───────────────────────────────────────────────────────────────────────

/** API shape from FastAPI TosVersionRead */
interface TosVersionApi {
  id: string;
  version_number: number;
  content_md: string;
  effective_at: string;
}

export interface TosVersion {
  id: string;
  version: number;
  content: string;
  effective_at: string;
}

function mapTosVersion(raw: TosVersionApi): TosVersion {
  return {
    id: raw.id,
    version: raw.version_number,
    content: raw.content_md,
    effective_at: raw.effective_at,
  };
}

export const tosApi = {
  getCurrent: async (token: string) =>
    mapTosVersion(await request<TosVersionApi>("/tos/current", {}, token)),
  acceptTos: (token: string, tosVersionId: string) =>
    request<{ accepted: boolean }>(
      "/users/me/accept-tos",
      { method: "POST", body: JSON.stringify({ tos_version_id: tosVersionId }) },
      token,
    ),
  list: async (token: string) =>
    (await request<TosVersionApi[]>("/admin/tos", {}, token)).map(mapTosVersion),
  publish: async (token: string, content: string) => {
    const raw = await request<{ id: string; version_number: number }>(
      "/admin/tos",
      { method: "POST", body: JSON.stringify({ content_md: content }) },
      token,
    );
    return { id: raw.id, version: raw.version_number };
  },
  listDisclaimer: async (token: string): Promise<TosVersion[]> => {
    const raw = await request<Array<{ id: string; version_number: number; content: string; effective_at: string }>>(
      "/admin/disclaimer",
      {},
      token,
    );
    return raw.map((d) => ({ id: d.id, version: d.version_number, content: d.content, effective_at: d.effective_at }));
  },
  publishDisclaimer: async (token: string, content: string) => {
    const raw = await request<{ id: string; version_number: number }>(
      "/admin/disclaimer",
      { method: "POST", body: JSON.stringify({ content }) },
      token,
    );
    return { id: raw.id, version: raw.version_number };
  },
};

// ── Exam Syllabi ──────────────────────────────────────────────────────────────

export interface Syllabus {
  id: string;
  name: string;
  description: string | null;
  version: number;
  is_active: boolean;
}

export const syllabiApi = {
  list: (token: string) =>
    request<Syllabus[]>("/admin/exam-syllabi", {}, token),
  create: (token: string, data: { name: string; description?: string }) =>
    request<Syllabus>(
      "/admin/exam-syllabi",
      { method: "POST", body: JSON.stringify(data) },
      token,
    ),
  update: (token: string, id: string, data: Partial<Syllabus>) =>
    request<Syllabus>(
      `/admin/exam-syllabi/${id}`,
      { method: "PUT", body: JSON.stringify(data) },
      token,
    ),
  delete: (token: string, id: string) =>
    request<void>(`/admin/exam-syllabi/${id}`, { method: "DELETE" }, token),
};

// ── Personas ──────────────────────────────────────────────────────────────────

export interface Persona {
  id: string;
  name: string;
  description: string | null;
  system_prompt: string;
  is_custom: boolean;
  is_active: boolean;
}

export const personasApi = {
  list: (token: string) =>
    request<Persona[]>("/admin/personas", {}, token),
  update: (
    token: string,
    id: string,
    data: { system_prompt?: string; description?: string; is_active?: boolean },
  ) =>
    request<Persona>(
      `/admin/personas/${id}`,
      { method: "PUT", body: JSON.stringify(data) },
      token,
    ),
};

// ── Subscription Tiers ────────────────────────────────────────────────────────

export interface SubscriptionTier {
  id: string;
  name: string;
  pricing_monthly_pkr: number;
  caps: Record<string, unknown>;
  applies_to_role: string;
  is_active: boolean;
}

export const subscriptionsApi = {
  list: (token: string) =>
    request<SubscriptionTier[]>("/admin/subscription-tiers", {}, token),
  create: (token: string, data: Omit<SubscriptionTier, "id">) =>
    request<SubscriptionTier>(
      "/admin/subscription-tiers",
      { method: "POST", body: JSON.stringify(data) },
      token,
    ),
  update: (token: string, id: string, data: Partial<SubscriptionTier>) =>
    request<SubscriptionTier>(
      `/admin/subscription-tiers/${id}`,
      { method: "PUT", body: JSON.stringify(data) },
      token,
    ),
  delete: (token: string, id: string) =>
    request<void>(`/admin/subscription-tiers/${id}`, { method: "DELETE" }, token),
};

// ── Library ───────────────────────────────────────────────────────────────────

export interface LibraryBook {
  id: string;
  filename: string;
  status: "ingesting" | "available" | "ingestion_failed" | "soft_deleted";
  tags: { subject_id?: string; grade_range?: string[]; language?: string; content_type?: string };
  created_at: string;
}

export const libraryApi = {
  list: (token: string) =>
    request<LibraryBook[]>("/admin/library", {}, token),
  softDelete: (token: string, id: string) =>
    request<void>(`/admin/library/${id}`, { method: "DELETE" }, token),
};

// ── Audit Log ─────────────────────────────────────────────────────────────────

export interface AuditEntry {
  id: string;
  action: string;
  actor_id: string;
  target_type: string;
  target_id: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
}

export const auditApi = {
  list: (token: string, params?: { actor?: string; action?: string }) => {
    const qs = params
      ? "?" + new URLSearchParams(params as Record<string, string>).toString()
      : "";
    return request<AuditEntry[]>(`/admin/audit-log${qs}`, {}, token);
  },
};

// ── Notifications ─────────────────────────────────────────────────────────────

export interface Notification {
  id: string;
  feature_namespace: string;
  title: string;
  body: string;
  is_read: boolean;
  created_at: string;
}

export const notificationsApi = {
  list: async (token: string): Promise<Notification[]> => {
    const res = await request<{ items: Notification[]; total: number; unread_count: number }>(
      "/notifications",
      {},
      token,
    );
    return res.items;
  },
  markRead: (token: string, id: string) =>
    request<void>(`/notifications/${id}/read`, { method: "POST" }, token),
};
