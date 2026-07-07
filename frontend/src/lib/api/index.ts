/**
 * Typed API client for the IqbalAI FastAPI backend.
 * All fetch calls go through here — never use raw fetch() in components.
 */

import type {
  AcceptInviteRequest,
  AdminUserInviteCreate,
  DisclaimerVersionCreate,
  DisclaimerVersionRead,
  DistrictCreate,
  DistrictUpdate,
  ExamSyllabusCreate,
  ExamSyllabusRead,
  ExamSyllabusUpdate,
  ExamFrameworkCreate,
  ExamFrameworkRead,
  ExamFrameworkUpdate,
  FrameworkResearchJobRead,
  FrameworkStudyPlanRead,
  FrameworkRejectRequest,
  LibraryUploadParams,
  LibraryUploadResponse,
  Notification,
  PersonaRead,
  PersonaUpdate,
  PostLoginResponse,
  SubjectCreate,
  SubjectRead,
  SubjectUpdate,
  AcademicSessionCreate,
  AcademicSessionRead,
  ActiveSessionRead,
  GradeCreate,
  GradeRead,
  SectionCreate,
  SectionRead,
  StudentEnrollmentCreate,
  StudentEnrollmentRead,
  OfferingCreate,
  OfferingRead,
  OfferingAssign,
  EligibleTeacherRead,
  TeacherOnboardingRead,
  TeacherCapacityUpdate,
  TeacherCapacityUpdateRead,
  TeacherProfileComplete,
  SchoolStudentOnboardingRead,
  StudentProfileBasicComplete,
  StudentModeSelect,
  SchoolCreate,
  SchoolUpdate,
  SubscriptionTierCreate,
  SubscriptionTierRead,
  SubscriptionTierUpdate,
  TosAcceptResponse,
  TosDeclineResponse,
  TosVersion,
  TosVersionCreate,
  TosVersionRead,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export type {
  Notification,
  PersonaRead as Persona,
  ExamSyllabusRead as Syllabus,
  ExamFrameworkRead as Framework,
  FrameworkResearchJobRead as FrameworkResearchJob,
  SubscriptionTierRead as SubscriptionTier,
  SubjectRead as Subject,
  SubjectCreate,
  SubjectUpdate,
  SubjectStatus,
  SchoolCreate,
  SchoolUpdate,
  GradeRead as Grade,
  GradeCreate,
  GradeStatus,
  SectionRead as Section,
  OfferingRead,
  EligibleTeacherRead,
  LibraryBookRead as LibraryBook,
  TosVersion,
} from "./types";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: unknown
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
  status: number
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

async function request<T>(path: string, options: RequestInit = {}, token?: string): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> | undefined),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (!res.ok) {
    let errorJson: {
      error?: { code?: string; message?: string };
      code?: string;
      message?: string;
      details?: unknown;
    } = {};
    try {
      errorJson = await res.json();
    } catch {
      // ignore parse errors
    }
    const err = errorJson.error ?? errorJson;
    throw new ApiError(
      res.status,
      err.code ?? "UNKNOWN_ERROR",
      err.message ?? `Request failed with status ${res.status}`,
      errorJson.details
    );
  }

  if (res.status === 204) return undefined as T;

  const envelope = await res.json();
  return (envelope.data ?? envelope) as T;
}

async function requestFormData<T>(path: string, formData: FormData, token?: string): Promise<T> {
  const headers: Record<string, string> = {};
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers,
    body: formData,
  });

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

export const authApi = {
  postLogin: (token: string) =>
    request<PostLoginResponse>("/auth/post-login", { method: "POST" }, token),

  acceptInvite: (data: AcceptInviteRequest) =>
    request<{ status: string; email?: string; message: string }>("/auth/accept-invite", {
      method: "POST",
      body: JSON.stringify(data),
    }),
};

// ── Independent signup ────────────────────────────────────────────────────────

export interface IndependentSignupInfo {
  roles: string[];
  languages: string[];
}

export interface IndependentSignupCreate {
  email: string;
  password: string;
  display_name: string;
  role: "independent_teacher" | "independent_student";
  language_preference: "en" | "ur" | "sd" | "ps";
  grade_level?: number;
  exam_syllabus_id?: string;
}

export interface IndependentSignupResponse {
  user_id: string;
  email: string;
  role: string;
  tenant_type: string;
  message: string;
}

export const independentSignupApi = {
  getInfo: () => request<IndependentSignupInfo>("/independent/signup"),
  signup: (data: IndependentSignupCreate) =>
    request<IndependentSignupResponse>("/independent/signup", {
      method: "POST",
      body: JSON.stringify(data),
    }),
};

// ── Parent signup ─────────────────────────────────────────────────────────────

export interface ParentSignupInfo {
  languages: string[];
}

export interface ParentSignupCreate {
  email: string;
  password: string;
  display_name: string;
  language_preference: "en" | "ur" | "sd" | "ps";
}

export interface ParentSignupResponse {
  user_id: string;
  email: string;
  role: string;
  tenant_type: string;
  parent_state: string;
  message: string;
}

export const parentSignupApi = {
  getInfo: () => request<ParentSignupInfo>("/parents/signup"),
  signup: (data: ParentSignupCreate) =>
    request<ParentSignupResponse>("/parents/signup", {
      method: "POST",
      body: JSON.stringify(data),
    }),
};

// ── Parent-child links ────────────────────────────────────────────────────────

export interface ParentChildLinkRead {
  id: string;
  parent_user_id: string;
  student_user_id: string;
  status: "pending" | "approved" | "revoked";
  parent_name?: string | null;
  student_name?: string | null;
  student_email?: string | null;
  approved_at?: string | null;
  revoked_at?: string | null;
  read_only_access: boolean;
  created_at: string;
}

export interface ParentConnectionsRead {
  parent_state: string;
  links: ParentChildLinkRead[];
}

export interface StudentLinkRequestList {
  pending: ParentChildLinkRead[];
}

export interface StudentConnectionsRead {
  access_state: string;
  linked_parents: ParentChildLinkRead[];
  link_history: ParentChildLinkRead[];
}

export interface ParentStudentAccessStateRead {
  student_user_id: string;
  access_state: string;
  read_only_access: boolean;
}

export const parentChildLinksApi = {
  getConnections: (token: string) =>
    request<ParentConnectionsRead>("/parents/me/connections", {}, token),
  createLinkRequest: (token: string, student_email: string) =>
    request<ParentChildLinkRead>(
      "/parents/me/link-requests",
      { method: "POST", body: JSON.stringify({ student_email }) },
      token
    ),
  revokeLink: (token: string, linkId: string) =>
    request<ParentChildLinkRead>(`/parents/me/links/${linkId}/revoke`, { method: "POST" }, token),
  getStudentAccessState: (token: string, studentUserId: string) =>
    request<ParentStudentAccessStateRead>(
      `/parents/me/students/${studentUserId}/access-state`,
      {},
      token
    ),
  listStudentPending: (token: string) =>
    request<StudentLinkRequestList>("/students/me/link-requests", {}, token),
  getStudentConnections: (token: string) =>
    request<StudentConnectionsRead>("/students/me/connections", {}, token),
  approveLinkRequest: (token: string, linkId: string) =>
    request<ParentChildLinkRead>(
      `/students/me/link-requests/${linkId}/approve`,
      { method: "POST" },
      token
    ),
  revokeParentLink: (token: string, linkId: string) =>
    request<ParentChildLinkRead>(`/students/me/links/${linkId}/revoke`, { method: "POST" }, token),
};

// ── Independent teacher onboarding ────────────────────────────────────────────

export interface IndependentTeacherOnboardingRead {
  state: "profile_incomplete" | "ready_to_use";
  profile_complete: boolean;
  ready_to_use: boolean;
  can_create_content: boolean;
  profile: {
    user_id: string;
    name: string;
    language_preference: string;
    profile_completed_at: string | null;
  } | null;
}

export interface IndependentTeacherProfileComplete {
  name: string;
  language_preference: "en" | "ur" | "sd" | "ps";
}

export const independentTeacherOnboardingApi = {
  getOnboarding: (token: string) =>
    request<IndependentTeacherOnboardingRead>("/independent/teachers/me/onboarding", {}, token),
  completeProfile: (token: string, data: IndependentTeacherProfileComplete) =>
    request<IndependentTeacherOnboardingRead>(
      "/independent/teachers/me/profile",
      { method: "PUT", body: JSON.stringify(data) },
      token
    ),
};

export interface ExamFrameworkOption {
  id: string;
  name: string;
  exam_board: string;
  language: string;
}

export interface IndependentStudentOnboardingRead {
  state: "profile_incomplete" | "ready_to_study";
  profile_complete: boolean;
  ready_to_study: boolean;
  self_study_only: boolean;
  profile: {
    user_id: string;
    name: string;
    language_preference: string;
    grade_level: number;
    exam_syllabus_id: string;
    exam_date: string | null;
    diagnostic_available: boolean;
    diagnostic_deferred: boolean;
  } | null;
}

export const independentStudentOnboardingApi = {
  listExamFrameworks: () =>
    request<ExamFrameworkOption[]>("/independent/students/me/exam-frameworks"),
  getOnboarding: (token: string) =>
    request<IndependentStudentOnboardingRead>("/independent/students/me/onboarding", {}, token),
  completeProfile: (token: string, data: { exam_date: string }) =>
    request<IndependentStudentOnboardingRead>(
      "/independent/students/me/profile",
      { method: "PUT", body: JSON.stringify(data) },
      token
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

// ── ToS ───────────────────────────────────────────────────────────────────────

export const tosApi = {
  getCurrent: async (token: string) =>
    mapTosVersion(await request<TosVersionRead>("/tos/current", {}, token)),
  acceptTos: (token: string, tosVersionId: string) =>
    request<TosAcceptResponse>(
      "/users/me/accept-tos",
      { method: "POST", body: JSON.stringify({ tos_version_id: tosVersionId }) },
      token
    ),
  declineTos: (token: string) =>
    request<TosDeclineResponse>(
      "/users/me/decline-tos",
      { method: "POST", body: JSON.stringify({}) },
      token
    ),
  list: async (token: string) =>
    (await request<TosVersionRead[]>("/admin/tos", {}, token)).map(mapTosVersion),
  publish: async (token: string, content: string) => {
    const payload: TosVersionCreate = { content_md: content, language: "en" };
    const raw = await request<TosVersionRead>(
      "/admin/tos",
      { method: "POST", body: JSON.stringify(payload) },
      token
    );
    return { id: raw.id, version: raw.version_number };
  },
  listDisclaimer: async (token: string) =>
    (await request<DisclaimerVersionRead[]>("/admin/disclaimer", {}, token)).map(mapDisclaimer),
  publishDisclaimer: async (token: string, content: string) => {
    const payload: DisclaimerVersionCreate = { content, language: "en" };
    const raw = await request<DisclaimerVersionRead>(
      "/admin/disclaimer",
      { method: "POST", body: JSON.stringify(payload) },
      token
    );
    return { id: raw.id, version: raw.version_number };
  },
};

// ── Exam Syllabi ──────────────────────────────────────────────────────────────

export const syllabiApi = {
  list: (token: string) => request<ExamSyllabusRead[]>("/admin/exam-syllabi", {}, token),
  create: (token: string, data: ExamSyllabusCreate) =>
    request<ExamSyllabusRead>(
      "/admin/exam-syllabi",
      { method: "POST", body: JSON.stringify(data) },
      token
    ),
  update: (token: string, id: string, data: ExamSyllabusUpdate) =>
    request<ExamSyllabusRead>(
      `/admin/exam-syllabi/${id}`,
      { method: "PUT", body: JSON.stringify(data) },
      token
    ),
  delete: (token: string, id: string) =>
    request<void>(`/admin/exam-syllabi/${id}`, { method: "DELETE" }, token),
};

// ── Exam Frameworks (T-092, Platform Admin) ───────────────────────────────────

export const frameworksApi = {
  list: (token: string) => request<ExamFrameworkRead[]>("/exam-frameworks/", {}, token),
  create: (token: string, data: ExamFrameworkCreate) =>
    request<ExamFrameworkRead>(
      "/exam-frameworks/",
      { method: "POST", body: JSON.stringify(data) },
      token
    ),
  update: (token: string, id: string, data: ExamFrameworkUpdate) =>
    request<ExamFrameworkRead>(
      `/exam-frameworks/${id}`,
      { method: "PUT", body: JSON.stringify(data) },
      token
    ),
  delete: (token: string, id: string) =>
    request<ExamFrameworkRead>(`/exam-frameworks/${id}`, { method: "DELETE" }, token),
  // T-093: kick off the Pattern-A AI research run for a DRAFT framework (202).
  triggerResearch: (token: string, id: string) =>
    request<FrameworkResearchJobRead>(`/exam-frameworks/${id}/research`, { method: "POST" }, token),
  // Latest research job for a framework (progress / result); 404 if none yet.
  latestResearch: (token: string, id: string) =>
    request<FrameworkResearchJobRead>(`/exam-frameworks/${id}/research`, {}, token),
  // T-094: read the plan pending approval (content + cited sources) for review.
  reviewPlan: (token: string, id: string) =>
    request<FrameworkStudyPlanRead>(`/exam-frameworks/${id}/plan`, {}, token),
  // T-094: approve the pending plan -> PUBLISHED (selectable by students).
  approve: (token: string, id: string) =>
    request<FrameworkStudyPlanRead>(`/exam-frameworks/${id}/approve`, { method: "POST" }, token),
  // T-094: reject the pending plan -> DRAFT with reviewer notes.
  reject: (token: string, id: string, data: FrameworkRejectRequest) =>
    request<FrameworkStudyPlanRead>(
      `/exam-frameworks/${id}/reject`,
      { method: "POST", body: JSON.stringify(data) },
      token
    ),
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
  create: (token: string, data: DistrictCreate) =>
    request<District>(
      "/admin/districts/",
      {
        method: "POST",
        body: JSON.stringify(data),
        // Idempotency-Key (ARCH §5.9): a retried POST (double-click, network retry)
        // returns the cached district instead of creating a duplicate.
        headers: { "Idempotency-Key": crypto.randomUUID() },
      },
      token
    ),
  update: (token: string, id: string, data: DistrictUpdate) =>
    request<District>(
      `/admin/districts/${id}`,
      { method: "PUT", body: JSON.stringify(data) },
      token
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
  invite: (token: string, data: AdminUserInviteCreate) =>
    request<UserInvite>(
      "/admin/users",
      {
        method: "POST",
        body: JSON.stringify(data),
        headers: { "Idempotency-Key": crypto.randomUUID() },
      },
      token
    ),
  resend: (token: string, inviteId: string) =>
    request<UserInvite>(`/admin/users/${inviteId}/resend`, { method: "POST" }, token),
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
      token
    ),
  create: (token: string, data: SchoolCreate) =>
    request<School>(
      "/admin/schools/",
      {
        method: "POST",
        body: JSON.stringify(data),
        headers: { "Idempotency-Key": crypto.randomUUID() },
      },
      token
    ),
  update: (token: string, id: string, data: SchoolUpdate) =>
    request<School>(`/admin/schools/${id}`, { method: "PUT", body: JSON.stringify(data) }, token),
  delete: (token: string, id: string) =>
    request<void>(`/admin/schools/${id}`, { method: "DELETE" }, token),
};

// ── School Admin (T-032) ────────────────────────────────────────────────────────

export const schoolAdminApi = {
  getMySchool: (token: string) => request<School>("/school/admin/school", {}, token),
  listAuditLog: async (token: string) => {
    const res = await request<{ items: AuditEntry[] }>("/school/admin/audit-log/", {}, token);
    return res.items ?? [];
  },
};

// ── Personas ──────────────────────────────────────────────────────────────────

export const personasApi = {
  list: (token: string) => request<PersonaRead[]>("/admin/personas", {}, token),
  update: (token: string, id: string, data: PersonaUpdate) =>
    request<PersonaRead>(
      `/admin/personas/${id}`,
      { method: "PUT", body: JSON.stringify(data) },
      token
    ),
};

// ── Subscription Tiers ────────────────────────────────────────────────────────

export const subscriptionsApi = {
  list: (token: string) => request<SubscriptionTierRead[]>("/admin/subscription-tiers", {}, token),
  create: (token: string, data: SubscriptionTierCreate) =>
    request<SubscriptionTierRead>(
      "/admin/subscription-tiers",
      { method: "POST", body: JSON.stringify(data) },
      token
    ),
  update: (token: string, id: string, data: SubscriptionTierUpdate) =>
    request<SubscriptionTierRead>(
      `/admin/subscription-tiers/${id}`,
      { method: "PUT", body: JSON.stringify(data) },
      token
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
      token
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
      token
    );
  },
  softDelete: (token: string, id: string) =>
    request<void>(`/admin/library/${id}`, { method: "DELETE" }, token),
};

// ── School library (teacher+) — T-055 ───────────────────────────────────────────

export interface SchoolLibraryUploadParams {
  file: File | Blob;
  fileName?: string;
  title: string;
  content_type?: string;
  language?: string;
  subject_id?: string | null;
  grade_level_ordinal?: number | null;
  visibility?: string;
}

export interface SchoolLibraryListParams {
  subject_id?: string;
  grade_level_ordinal?: number;
  language?: string;
  content_type?: string;
  title?: string;
  limit?: number;
  offset?: number;
}

export const schoolLibraryApi = {
  list: (token: string, params: SchoolLibraryListParams = {}) => {
    const qs = new URLSearchParams();
    if (params.subject_id) qs.set("subject_id", params.subject_id);
    if (params.grade_level_ordinal != null) {
      qs.set("grade_level_ordinal", String(params.grade_level_ordinal));
    }
    if (params.language) qs.set("language", params.language);
    if (params.content_type) qs.set("content_type", params.content_type);
    if (params.title) qs.set("title", params.title);
    if (params.limit != null) qs.set("limit", String(params.limit));
    if (params.offset != null) qs.set("offset", String(params.offset));
    const query = qs.toString();
    return request<import("./types").SchoolLibraryListResponse>(
      `/school/library${query ? `?${query}` : ""}`,
      {},
      token
    );
  },
  upload: (token: string, params: SchoolLibraryUploadParams) => {
    const qs = new URLSearchParams();
    qs.set("title", params.title);
    if (params.content_type) qs.set("content_type", params.content_type);
    if (params.language) qs.set("language", params.language);
    if (params.subject_id) qs.set("subject_id", params.subject_id);
    if (params.grade_level_ordinal != null) {
      qs.set("grade_level_ordinal", String(params.grade_level_ordinal));
    }
    if (params.visibility) qs.set("visibility", params.visibility);

    const formData = new FormData();
    const uploadName =
      params.fileName ?? (params.file instanceof File ? params.file.name : "upload.pdf");
    formData.append("file", params.file, uploadName);

    return requestFormData<import("./types").SchoolLibraryUploadResponse>(
      `/school/library?${qs.toString()}`,
      formData,
      token
    );
  },
  get: (token: string, itemId: string) =>
    request<import("./types").SchoolLibraryItemRead>(`/school/library/${itemId}`, {}, token),
  publish: (token: string, itemId: string) =>
    request<import("./types").SchoolLibraryItemRead>(
      `/school/library/${itemId}/publish`,
      { method: "POST" },
      token
    ),
  removeSelection: (token: string, itemId: string) =>
    request<import("./types").SchoolLibraryItemRead>(
      `/school/library/${itemId}/selection`,
      { method: "DELETE" },
      token
    ),
  deleteItem: (token: string, itemId: string) =>
    request<import("./types").SchoolLibraryItemRead>(
      `/school/library/${itemId}`,
      { method: "DELETE" },
      token
    ),
  retryIngestion: (token: string, itemId: string) =>
    request<import("./types").SchoolLibraryItemRead>(
      `/school/library/${itemId}/retry-ingestion`,
      { method: "POST" },
      token
    ),
};

// ── Audit Log ─────────────────────────────────────────────────────────────────

export interface AuditEntry {
  id: string;
  action: string;
  actor_id: string | null;
  target_type: string | null;
  target_id: string | null;
  metadata_json?: string | null;
  created_at: string;
}

export const auditApi = {
  list: async (token: string, params?: { actor?: string; action?: string }) => {
    const qs = params ? "?" + new URLSearchParams(params as Record<string, string>).toString() : "";
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
  status: "valid" | "invalid" | "enrolled" | "failed";
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
    let errorJson: {
      error?: { code?: string; message?: string };
      code?: string;
      message?: string;
    } = {};
    try {
      errorJson = await res.json();
    } catch {
      // ignore
    }
    const err = errorJson.error ?? errorJson;
    throw new ApiError(
      res.status,
      err.code ?? "UNKNOWN_ERROR",
      err.message ?? `Request failed with status ${res.status}`
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
  commit: (token: string, importId: string) =>
    request<BulkImportJob>(
      `/coordinator/bulk-imports/${importId}/commit`,
      { method: "POST" },
      token
    ),
};

// ── Subjects (Coordinator) — T-041 ──────────────────────────────────────────────

export const subjectsApi = {
  list: (token: string, includeArchived = false) =>
    request<SubjectRead[]>(
      includeArchived ? "/subjects/?include_archived=true" : "/subjects/",
      {},
      token
    ),
  create: (token: string, data: SubjectCreate) =>
    request<SubjectRead>(
      "/subjects/",
      {
        method: "POST",
        body: JSON.stringify(data),
        // Idempotency-Key (ARCH §5.9): a retried POST (double-click, network retry)
        // returns the cached subject instead of creating a duplicate.
        headers: { "Idempotency-Key": crypto.randomUUID() },
      },
      token
    ),
  update: (token: string, id: string, data: SubjectUpdate) =>
    request<SubjectRead>(`/subjects/${id}`, { method: "PUT", body: JSON.stringify(data) }, token),
  archive: (token: string, id: string) =>
    request<SubjectRead>(`/subjects/${id}/archive`, { method: "POST" }, token),
};

// ── Teacher onboarding — T-053 ────────────────────────────────────────────────

export const teacherOnboardingApi = {
  getOnboarding: (token: string) =>
    request<TeacherOnboardingRead>("/teachers/me/onboarding", {}, token),
  completeProfile: (token: string, data: TeacherProfileComplete) =>
    request<TeacherOnboardingRead>(
      "/teachers/me/profile",
      { method: "PUT", body: JSON.stringify(data) },
      token
    ),
  listSubjectOptions: (token: string) =>
    request<SubjectRead[]>("/teachers/me/subject-options", {}, token),
  updateCapacity: (token: string, data: TeacherCapacityUpdate) =>
    request<TeacherCapacityUpdateRead>(
      "/teachers/me/capacity",
      { method: "PATCH", body: JSON.stringify(data) },
      token
    ),
};

export const studentOnboardingApi = {
  getOnboarding: (token: string) =>
    request<SchoolStudentOnboardingRead>("/students/me/onboarding", {}, token),
  completeProfileBasic: (token: string, data: StudentProfileBasicComplete) =>
    request<SchoolStudentOnboardingRead>(
      "/students/me/onboarding/profile-basic",
      { method: "PUT", body: JSON.stringify(data) },
      token
    ),
  selectModes: (token: string, data: StudentModeSelect) =>
    request<SchoolStudentOnboardingRead>(
      "/students/me/onboarding/modes",
      { method: "PUT", body: JSON.stringify(data) },
      token
    ),
  dismissBanner: (token: string) =>
    request<SchoolStudentOnboardingRead>(
      "/students/me/onboarding/dismiss-banner",
      { method: "POST", body: JSON.stringify({ dismissed: true }) },
      token
    ),
  setExamDate: (token: string, exam_date: string) =>
    request<SchoolStudentOnboardingRead>(
      "/students/me/onboarding/exam-date",
      { method: "PUT", body: JSON.stringify({ exam_date }) },
      token
    ),
};

export interface DataRightsRequestRead {
  id: string;
  request_type: "export" | "deletion";
  status: string;
  requested_at: string;
  ready_at?: string | null;
  expires_at?: string | null;
  deletion_scheduled_at?: string | null;
  completed_at?: string | null;
  cancelled_at?: string | null;
  download_available: boolean;
}

export interface DataRightsStatusRead {
  export_request?: DataRightsRequestRead | null;
  deletion_request?: DataRightsRequestRead | null;
  export_policy_message: string;
  deletion_policy_message: string;
}

async function downloadRequest(path: string, token: string): Promise<Blob> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    let message = `Request failed with status ${res.status}`;
    try {
      const body = (await res.json()) as { error?: { message?: string } };
      if (body.error?.message) message = body.error.message;
    } catch {
      // ignore parse errors
    }
    throw new Error(message);
  }
  return res.blob();
}

export const dataRightsApi = {
  getStudentStatus: (token: string) =>
    request<DataRightsStatusRead>("/students/me/data-rights", {}, token),
  requestStudentExport: (token: string) =>
    request<DataRightsRequestRead>("/students/me/data-rights/export", { method: "POST" }, token),
  downloadStudentExport: (token: string, requestId: string) =>
    downloadRequest(`/students/me/data-rights/export/${requestId}/download`, token),
  requestStudentDeletion: (token: string, confirm: boolean) =>
    request<DataRightsRequestRead>(
      "/students/me/data-rights/deletion",
      { method: "POST", body: JSON.stringify({ confirm }) },
      token
    ),
  cancelStudentDeletion: (token: string, requestId: string) =>
    request<DataRightsRequestRead>(
      `/students/me/data-rights/deletion/${requestId}/cancel`,
      { method: "POST" },
      token
    ),
  getParentStatus: (token: string) =>
    request<DataRightsStatusRead>("/parents/me/data-rights", {}, token),
  requestParentExport: (token: string) =>
    request<DataRightsRequestRead>("/parents/me/data-rights/export", { method: "POST" }, token),
  downloadParentExport: (token: string, requestId: string) =>
    downloadRequest(`/parents/me/data-rights/export/${requestId}/download`, token),
  requestParentDeletion: (token: string, confirm: boolean) =>
    request<DataRightsRequestRead>(
      "/parents/me/data-rights/deletion",
      { method: "POST", body: JSON.stringify({ confirm }) },
      token
    ),
  cancelParentDeletion: (token: string, requestId: string) =>
    request<DataRightsRequestRead>(
      `/parents/me/data-rights/deletion/${requestId}/cancel`,
      { method: "POST" },
      token
    ),
};

// ── Academic Sessions (Coordinator) — T-042 ─────────────────────────────────────

export const academicSessionsApi = {
  list: (token: string) => request<AcademicSessionRead[]>("/academic-sessions/", {}, token),
  getActive: (token: string) => request<ActiveSessionRead>("/academic-sessions/active", {}, token),
  create: (token: string, data: AcademicSessionCreate) =>
    request<AcademicSessionRead>(
      "/academic-sessions/",
      {
        method: "POST",
        body: JSON.stringify(data),
        headers: { "Idempotency-Key": crypto.randomUUID() },
      },
      token
    ),
  activate: (token: string, id: string) =>
    request<AcademicSessionRead>(`/academic-sessions/${id}/activate`, { method: "POST" }, token),
};

// ── Grades (Coordinator) — T-043 ────────────────────────────────────────────────

export const gradesApi = {
  list: (token: string, includeArchived = false) =>
    request<GradeRead[]>(
      includeArchived ? "/grades/?include_archived=true" : "/grades/",
      {},
      token
    ),
  create: (token: string, data: GradeCreate) =>
    request<GradeRead>(
      "/grades/",
      {
        method: "POST",
        body: JSON.stringify(data),
        headers: { "Idempotency-Key": crypto.randomUUID() },
      },
      token
    ),
  get: (token: string, id: string) => request<GradeRead>(`/grades/${id}`, {}, token),
  archive: (token: string, id: string) =>
    request<GradeRead>(`/grades/${id}/archive`, { method: "POST" }, token),
};

// ── Sections (Coordinator) — T-044 ──────────────────────────────────────────────

export const sectionsApi = {
  list: (token: string, gradeId: string) =>
    request<SectionRead[]>(`/grades/${gradeId}/sections/`, {}, token),
  create: (token: string, gradeId: string, data: SectionCreate) =>
    request<SectionRead>(
      `/grades/${gradeId}/sections/`,
      {
        method: "POST",
        body: JSON.stringify(data),
        headers: { "Idempotency-Key": crypto.randomUUID() },
      },
      token
    ),
  archive: (token: string, gradeId: string, sectionId: string) =>
    request<SectionRead>(
      `/grades/${gradeId}/sections/${sectionId}/archive`,
      { method: "POST" },
      token
    ),
};

// ── Offerings (Coordinator) — T-045/T-046 ───────────────────────────────────────

export const offeringsApi = {
  list: (token: string, gradeId: string) =>
    request<OfferingRead[]>(`/grades/${gradeId}/offerings/`, {}, token),
  create: (token: string, gradeId: string, data: OfferingCreate) =>
    request<OfferingRead>(
      `/grades/${gradeId}/offerings/`,
      {
        method: "POST",
        body: JSON.stringify(data),
        headers: { "Idempotency-Key": crypto.randomUUID() },
      },
      token
    ),
  archive: (token: string, gradeId: string, offeringId: string) =>
    request<OfferingRead>(
      `/grades/${gradeId}/offerings/${offeringId}/archive`,
      { method: "POST" },
      token
    ),
  eligibleTeachers: (token: string, gradeId: string) =>
    request<EligibleTeacherRead[]>(`/grades/${gradeId}/offerings/eligible-teachers`, {}, token),
  assign: (
    token: string,
    gradeId: string,
    offeringId: string,
    data: OfferingAssign,
    ifMatch: string
  ) =>
    request<OfferingRead>(
      `/grades/${gradeId}/offerings/${offeringId}/assign`,
      { method: "POST", body: JSON.stringify(data), headers: { "If-Match": ifMatch } },
      token
    ),
  unassign: (token: string, gradeId: string, offeringId: string, ifMatch: string) =>
    request<OfferingRead>(
      `/grades/${gradeId}/offerings/${offeringId}/unassign`,
      { method: "POST", headers: { "If-Match": ifMatch } },
      token
    ),
};

// ── Student enrollments (Coordinator) — T-077 ─────────────────────────────────

export const studentEnrollmentsApi = {
  enroll: (token: string, gradeId: string, data: StudentEnrollmentCreate) =>
    request<StudentEnrollmentRead>(
      `/grades/${gradeId}/enrollments/`,
      {
        method: "POST",
        body: JSON.stringify(data),
        headers: { "Idempotency-Key": crypto.randomUUID() },
      },
      token
    ),
};
