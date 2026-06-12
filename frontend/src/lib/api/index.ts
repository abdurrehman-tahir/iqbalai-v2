/**
 * Typed API client for the IqbalAI FastAPI backend.
 * All fetch calls go through here — never use raw fetch() in components.
 */

import type {
  DisclaimerVersionRead,
  ExamSyllabusCreate,
  ExamSyllabusRead,
  ExamSyllabusUpdate,
  LibraryUploadParams,
  LibraryUploadResponse,
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
  return (envelope.data ?? envelope) as T;
}

async function requestFormData<T>(
  path: string,
  formData: FormData,
  token?: string,
): Promise<T> {
  const headers: Record<string, string> = {};
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

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
  listAuditLog: async (token: string) => {
    const res = await request<{ items: AuditEntry[] }>(
      "/school/admin/audit-log/",
      {},
      token,
    );
    return res.items ?? [];
  },
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
  upload: (token: string, params: LibraryUploadParams) => {
    const qs = new URLSearchParams();
    qs.set("title", params.title);
    if (params.content_type) qs.set("content_type", params.content_type);
    if (params.subject_tag) qs.set("subject_tag", params.subject_tag);
    if (params.grade_range_min != null) {
      qs.set("grade_range_min", String(params.grade_range_min));
    }
    if (params.grade_range_max != null) {
      qs.set("grade_range_max", String(params.grade_range_max));
    }
    if (params.language) qs.set("language", params.language);

    const formData = new FormData();
    formData.append("file", params.file);

    return requestFormData<LibraryUploadResponse>(
      `/admin/library?${qs.toString()}`,
      formData,
      token,
    );
  },
  softDelete: (token: string, id: string) =>
    request<void>(`/admin/library/${id}`, { method: "DELETE" }, token),
};

// ── Audit Log ─────────────────────────────────────────────────────────────────

export interface AuditEntry {
  id: string;
  action: string;
  actor_id: string | null;
  target_type: string | null;
  target_id: string | null;
  created_at: string;
}

export const auditApi = {
  list: async (token: string, params?: { actor?: string; action?: string }) => {
    const qs = params
      ? "?" + new URLSearchParams(params as Record<string, string>).toString()
      : "";
    const res = await request<{ items: AuditEntry[] }>(`/admin/audit-log${qs}`, {}, token);
    return res.items ?? [];
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
