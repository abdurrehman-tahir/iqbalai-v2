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
    let body: { error?: { code?: string; message?: string }; code?: string; message?: string; details?: unknown } = {};
    try {
      body = await res.json();
    } catch {
      // ignore parse errors
    }
    const err = body.error ?? body;
    throw new ApiError(
      res.status,
      err.code ?? "UNKNOWN_ERROR",
      err.message ?? `Request failed with status ${res.status}`,
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
      district_id?: string | null;
      school_id?: string | null;
      is_first_login: boolean;
      tos_acceptance_required: boolean;
      current_tos_version_id: string | null;
    }>("/auth/post-login", { method: "POST" }, token),

  acceptInvite: (data: {
    token: string;
    action: "accept" | "reject";
    password?: string;
    display_name?: string;
  }) =>
    request<{ status: string; email?: string; message: string }>(
      "/auth/accept-invite",
      { method: "POST", body: JSON.stringify(data) },
    ),
};

// ── Users ─────────────────────────────────────────────────────────────────────

export interface UserProfile {
  id: string;
  email: string;
  display_name: string;
  role: string;
  status: string;
  scoped_ids: string | null;
  district_id: string | null;
  school_id: string | null;
  created_at: string;
}

export const usersApi = {
  getMe: (token: string) => request<UserProfile>("/users/me", {}, token),
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

// ── Districts ─────────────────────────────────────────────────────────────────

export interface District {
  id: string;
  name: string;
  region: string | null;
  language_preference: string | null;
  created_at: string;
}

export const districtsApi = {
  list: (token: string) => request<District[]>("/admin/districts/", {}, token),
  create: (
    token: string,
    data: { name: string; region?: string; language_preference?: string },
  ) =>
    request<District>(
      "/admin/districts/",
      {
        method: "POST",
        body: JSON.stringify(data),
        // Idempotency-Key (ARCH §5.9): a retried POST (double-click, network retry)
        // returns the cached district instead of creating a duplicate.
        headers: { "Idempotency-Key": crypto.randomUUID() },
      },
      token,
    ),
  update: (
    token: string,
    id: string,
    data: { name?: string; region?: string; language_preference?: string },
  ) =>
    request<District>(
      `/admin/districts/${id}`,
      { method: "PUT", body: JSON.stringify(data) },
      token,
    ),
  delete: (token: string, id: string) =>
    request<void>(`/admin/districts/${id}`, { method: "DELETE" }, token),
};

// ── Admin user invites (T-030) ────────────────────────────────────────────────

export interface UserInvite {
  id: string;
  email: string;
  display_name: string;
  invited_role: string;
  district_id: string | null;
  school_id: string | null;
  status: string;
  expires_at: string;
  resent_count: number;
  created_at: string;
}

export interface AdminUser {
  id: string;
  email: string;
  display_name: string;
  role: string;
  status: string;
  district_id: string | null;
  school_id: string | null;
  scoped_ids: string | null;
  created_at: string;
}

export const adminUsersApi = {
  list: (token: string) => request<AdminUser[]>("/admin/users/", {}, token),
  suspend: (token: string, userId: string) =>
    request<AdminUser>(`/admin/users/${userId}/suspend`, { method: "POST" }, token),
  reactivate: (token: string, userId: string) =>
    request<AdminUser>(`/admin/users/${userId}/reactivate`, { method: "POST" }, token),
  deactivate: (token: string, userId: string) =>
    request<AdminUser>(`/admin/users/${userId}/deactivate`, { method: "POST" }, token),
  invite: (
    token: string,
    data: {
      email: string;
      display_name: string;
      role: string;
      district_id?: string;
      school_id?: string;
      grade_scope?: string[];
    },
  ) =>
    request<UserInvite>(
      "/admin/users",
      {
        method: "POST",
        body: JSON.stringify(data),
        headers: { "Idempotency-Key": crypto.randomUUID() },
      },
      token,
    ),
  resend: (token: string, inviteId: string) =>
    request<UserInvite>(
      `/admin/users/${inviteId}/resend`,
      { method: "POST" },
      token,
    ),
};

// ── Schools (T-031) ─────────────────────────────────────────────────────────────

export interface School {
  id: string;
  district_id: string;
  name: string;
  created_at: string;
}

export const schoolsApi = {
  list: (token: string, districtId?: string) =>
    request<School[]>(
      districtId
        ? `/admin/schools/?district_id=${encodeURIComponent(districtId)}`
        : "/admin/schools/",
      {},
      token,
    ),
  create: (token: string, data: { name: string; district_id: string }) =>
    request<School>(
      "/admin/schools/",
      {
        method: "POST",
        body: JSON.stringify(data),
        headers: { "Idempotency-Key": crypto.randomUUID() },
      },
      token,
    ),
  update: (token: string, id: string, data: { name?: string }) =>
    request<School>(
      `/admin/schools/${id}`,
      { method: "PUT", body: JSON.stringify(data) },
      token,
    ),
  delete: (token: string, id: string) =>
    request<void>(`/admin/schools/${id}`, { method: "DELETE" }, token),
};

// ── School Admin (T-032) ────────────────────────────────────────────────────────

export const schoolAdminApi = {
  getMySchool: (token: string) =>
    request<School>("/school/admin/school", {}, token),
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

// ── Bulk Import (Coordinator) ─────────────────────────────────────────────────

export interface BulkImportRowResult {
  row_number: number;
  status: "valid" | "invalid";
  errors: string[];
  data: Record<string, string> | null;
}

export interface BulkImportJob {
  id: string;
  school_id: string;
  imported_by_user_id: string;
  upload_id: string;
  total_rows: number;
  success_rows: number;
  failed_rows: number;
  status: string;
  rows: BulkImportRowResult[];
  created_at: string;
  completed_at: string | null;
}

async function uploadRequest<T>(path: string, formData: FormData, token: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  });

  if (!res.ok) {
    let body: { error?: { code?: string; message?: string }; code?: string; message?: string } = {};
    try {
      body = await res.json();
    } catch {
      // ignore
    }
    const err = body.error ?? body;
    throw new ApiError(
      res.status,
      err.code ?? "UNKNOWN_ERROR",
      err.message ?? `Request failed with status ${res.status}`,
    );
  }

  const envelope = await res.json();
  return (envelope.data ?? envelope) as T;
}

export const bulkImportApi = {
  dryRun: (token: string, file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return uploadRequest<BulkImportJob>("/coordinator/bulk-imports/", formData, token);
  },
  get: (token: string, importId: string) =>
    request<BulkImportJob>(`/coordinator/bulk-imports/${importId}`, {}, token),
};
