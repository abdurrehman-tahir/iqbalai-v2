import type { Page, Route } from "@playwright/test";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
const AUTHENTIK_BASE = process.env.NEXT_PUBLIC_AUTHENTIK_URL ?? "http://localhost:9000";

interface Syllabus {
  id: string;
  name: string;
  exam_board: string;
  region: string | null;
  grade_range_min: number | null;
  grade_range_max: number | null;
  language: string;
  version_number: number;
  is_active: boolean;
  created_at: string;
}

interface SubscriptionTier {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  applies_to: string;
  pricing_monthly_pkr: number;
  caps: Record<string, unknown> | null;
  is_active: boolean;
  created_at: string;
}

interface Persona {
  id: string;
  name: string;
  slug: string;
  system_prompt_en: string;
  is_custom: boolean;
  is_active: boolean;
  created_at: string;
}

interface AuditEntry {
  id: string;
  action: string;
  actor_id: string | null;
  actor_role: string | null;
  target_type: string | null;
  target_id: string | null;
  school_id: string | null;
  district_id: string | null;
  metadata_json: string | null;
  ip_address: string | null;
  created_at: string;
}

interface MockState {
  userId: string;
  email: string;
  tosAccepted: boolean;
  tosVersionId: string;
  tosContent: string;
  syllabi: Syllabus[];
  tiers: SubscriptionTier[];
  personas: Persona[];
  auditLog: AuditEntry[];
  notifications: Array<{
    id: string;
    feature_namespace: string;
    title: string;
    body: string;
    is_read: boolean;
    created_at: string;
  }>;
  library: Array<{
    id: string;
    filename: string;
    status: string;
    tags: Record<string, unknown>;
    created_at: string;
  }>;
  tosVersions: Array<{ id: string; version: number; content: string; effective_at: string }>;
  disclaimerVersions: Array<{ id: string; version: number; content: string; effective_at: string }>;
}

function envelope<T>(data: T) {
  return JSON.stringify({ data, message: "ok" });
}

function audit(
  state: MockState,
  action: string,
  targetType: string,
  targetId: string | null = null,
  metadata: Record<string, unknown> = {},
) {
  state.auditLog.unshift({
    id: `audit-${state.auditLog.length + 1}`,
    action,
    actor_id: state.userId,
    actor_role: "platform_admin",
    target_type: targetType,
    target_id: targetId,
    school_id: null,
    district_id: null,
    metadata_json: JSON.stringify(metadata),
    ip_address: null,
    created_at: new Date().toISOString(),
  });
}

function createInitialState(): MockState {
  const tosVersionId = "tos-v1";
  return {
    userId: "user-platform-admin-1",
    email: "admin@iqbalai.test",
    tosAccepted: false,
    tosVersionId,
    tosContent:
      "IqbalAI Platform Terms of Service (E2E fixture).\n\nScroll to the bottom to accept.",
    syllabi: [],
    tiers: [],
    personas: [
      {
        id: "persona-1",
        name: "Strict",
        slug: "strict",
        system_prompt_en: "You are a strict teacher.",
        is_custom: false,
        is_active: true,
        created_at: new Date().toISOString(),
      },
      {
        id: "persona-2",
        name: "Friendly Tutor",
        slug: "friendly-tutor",
        system_prompt_en: "You are a friendly tutor.",
        is_custom: false,
        is_active: true,
        created_at: new Date().toISOString(),
      },
      {
        id: "persona-3",
        name: "Storyteller",
        slug: "storyteller",
        system_prompt_en: "You teach through stories.",
        is_custom: false,
        is_active: true,
        created_at: new Date().toISOString(),
      },
      {
        id: "persona-4",
        name: "Exam Coach",
        slug: "exam-coach",
        system_prompt_en: "You focus on exam preparation.",
        is_custom: false,
        is_active: true,
        created_at: new Date().toISOString(),
      },
      {
        id: "persona-5",
        name: "Custom",
        slug: "custom",
        system_prompt_en: "Managed by platform batch job.",
        is_custom: true,
        is_active: true,
        created_at: new Date().toISOString(),
      },
    ],
    auditLog: [
      {
        id: "audit-bootstrap",
        action: "user.created",
        actor_id: "system",
        actor_role: null,
        target_type: "user",
        target_id: "user-platform-admin-1",
        school_id: null,
        district_id: null,
        metadata_json: JSON.stringify({ role: "platform_admin" }),
        ip_address: null,
        created_at: new Date().toISOString(),
      },
    ],
    notifications: [],
    library: [],
    tosVersions: [],
    disclaimerVersions: [],
  };
}

async function handleApiRoute(state: MockState, route: Route) {
  const request = route.request();
  const url = new URL(request.url());
  let path = url.pathname.replace("/api/v1", "");
  if (path.length > 1 && path.endsWith("/")) {
    path = path.slice(0, -1);
  }
  const method = request.method();

  if (method === "POST" && path === "/auth/post-login") {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: envelope({
        user_id: state.userId,
        email: state.email,
        role: "platform_admin",
        is_first_login: !state.tosAccepted,
        tos_acceptance_required: !state.tosAccepted,
        current_tos_version_id: state.tosVersionId,
      }),
    });
    return;
  }

  if (method === "GET" && path === "/tos/current") {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: envelope({
        id: state.tosVersionId,
        version_number: 1,
        content_md: state.tosContent,
        language: "en",
        effective_at: new Date().toISOString(),
      }),
    });
    return;
  }

  if (method === "POST" && path === "/users/me/decline-tos") {
    state.tosAccepted = false;
    audit(state, "tos.declined", "tos_version", state.tosVersionId);
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: envelope({ declined: true, status: "suspended" }),
    });
    return;
  }

  if (method === "POST" && path === "/users/me/accept-tos") {
    state.tosAccepted = true;
    audit(state, "tos.accepted", "tos_version", state.tosVersionId);
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: envelope({ accepted: true }),
    });
    return;
  }

  if (method === "GET" && path === "/admin/exam-syllabi") {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: envelope(state.syllabi),
    });
    return;
  }

  if (method === "POST" && path === "/admin/exam-syllabi") {
    const body = (await request.postDataJSON()) as {
      name: string;
      exam_board: string;
      language?: string;
    };
    const syllabus: Syllabus = {
      id: `syllabus-${state.syllabi.length + 1}`,
      name: body.name,
      exam_board: body.exam_board,
      region: null,
      grade_range_min: null,
      grade_range_max: null,
      language: body.language ?? "en",
      version_number: 1,
      is_active: true,
      created_at: new Date().toISOString(),
    };
    state.syllabi.push(syllabus);
    audit(state, "exam_syllabus.created", "exam_syllabus", syllabus.id, { name: body.name });
    await route.fulfill({
      status: 201,
      contentType: "application/json",
      body: envelope(syllabus),
    });
    return;
  }

  if (method === "GET" && path === "/admin/personas") {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: envelope(state.personas),
    });
    return;
  }

  if (method === "PUT" && path.startsWith("/admin/personas/")) {
    const id = path.split("/").pop()!;
    const body = (await request.postDataJSON()) as { system_prompt_en?: string };
    const persona = state.personas.find((p) => p.id === id);
    if (persona && body.system_prompt_en) {
      persona.system_prompt_en = body.system_prompt_en;
    }
    audit(state, "persona.updated", "persona", id);
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: envelope(persona ?? state.personas[0]),
    });
    return;
  }

  if (method === "GET" && path === "/admin/subscription-tiers") {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: envelope(state.tiers),
    });
    return;
  }

  if (method === "POST" && path === "/admin/subscription-tiers") {
    const body = (await request.postDataJSON()) as {
      name: string;
      slug: string;
      applies_to: string;
      pricing_monthly_pkr: number;
      caps?: Record<string, unknown> | null;
    };
    const tier: SubscriptionTier = {
      id: `tier-${state.tiers.length + 1}`,
      name: body.name,
      slug: body.slug,
      description: null,
      applies_to: body.applies_to,
      pricing_monthly_pkr: body.pricing_monthly_pkr,
      caps: body.caps ?? null,
      is_active: true,
      created_at: new Date().toISOString(),
    };
    state.tiers.push(tier);
    audit(state, "subscription_tier.created", "subscription_tier", tier.id, { name: body.name });
    await route.fulfill({
      status: 201,
      contentType: "application/json",
      body: envelope(tier),
    });
    return;
  }

  if (method === "GET" && path === "/admin/tos") {
    // Real backend wraps a list of TosVersionRead (content_md / version_number / language).
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: envelope(
        state.tosVersions.map((v) => ({
          id: v.id,
          version_number: v.version,
          content_md: v.content,
          language: "en",
          effective_at: v.effective_at,
        })),
      ),
    });
    return;
  }

  if (method === "POST" && path === "/admin/tos") {
    const body = (await request.postDataJSON()) as { content_md: string };
    const version = state.tosVersions.length + 1;
    const entry = {
      id: `tos-v${version}`,
      version,
      content: body.content_md,
      effective_at: new Date().toISOString(),
    };
    state.tosVersions.unshift(entry);
    audit(state, "tos.published", "tos_version", entry.id, { version });
    await route.fulfill({
      status: 201,
      contentType: "application/json",
      body: envelope({
        id: entry.id,
        version_number: version,
        content_md: body.content_md,
        language: "en",
        effective_at: entry.effective_at,
      }),
    });
    return;
  }

  if (method === "GET" && path === "/admin/disclaimer") {
    // Real backend wraps a list of DisclaimerVersionRead (content / version_number / language).
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: envelope(
        state.disclaimerVersions.map((v) => ({
          id: v.id,
          version_number: v.version,
          content: v.content,
          language: "en",
          effective_at: v.effective_at,
        })),
      ),
    });
    return;
  }

  if (method === "POST" && path === "/admin/disclaimer") {
    const body = (await request.postDataJSON()) as { content: string };
    const version = state.disclaimerVersions.length + 1;
    const entry = {
      id: `disclaimer-v${version}`,
      version,
      content: body.content,
      effective_at: new Date().toISOString(),
    };
    state.disclaimerVersions.unshift(entry);
    audit(state, "disclaimer.published", "disclaimer_version", entry.id, { version });
    await route.fulfill({
      status: 201,
      contentType: "application/json",
      body: envelope({
        id: entry.id,
        version_number: version,
        content: body.content,
        language: "en",
        effective_at: entry.effective_at,
      }),
    });
    return;
  }

  if (method === "POST" && path === "/admin/library") {
    const title = url.searchParams.get("title") ?? "upload.pdf";
    const bookId = `lib-${state.library.length + 1}`;
    const now = new Date().toISOString();
    state.library.unshift({
      id: bookId,
      filename: title,
      status: "processing",
      tags: {
        language: url.searchParams.get("language") ?? "en",
        content_type: url.searchParams.get("content_type") ?? "curriculum",
      },
      created_at: now,
    });
    await route.fulfill({
      status: 202,
      contentType: "application/json",
      body: JSON.stringify({
        book_id: bookId,
        upload_id: `upload-${bookId}`,
        status: "processing",
        message: "Upload accepted; ingestion queued on the ingestion worker.",
      }),
    });
    return;
  }

  if (method === "GET" && path === "/admin/library") {
    // LibraryBookListResponse is a bare {items, total} (no SuccessEnvelope data wrapper).
    const items = state.library.map((entry) => ({
      id: entry.id,
      upload_id: `upload-${entry.id}`,
      title: entry.filename,
      content_type: String(entry.tags.content_type ?? "curriculum"),
      subject_tag: null,
      grade_range_min: null,
      grade_range_max: null,
      language: String(entry.tags.language ?? "en"),
      sha256: "mock-sha256",
      status: entry.status,
      qdrant_collection: "platform_chunks",
      chunk_count: null,
      created_at: entry.created_at,
      updated_at: entry.created_at,
      deleted_at: null,
    }));
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items, total: items.length }),
    });
    return;
  }

  if (method === "GET" && path === "/admin/audit-log") {
    const actor = url.searchParams.get("actor");
    const action = url.searchParams.get("action");
    let entries = state.auditLog;
    if (actor) {
      entries = entries.filter((e) => e.actor_id?.includes(actor));
    }
    if (action) {
      entries = entries.filter((e) => e.action.includes(action));
    }
    const items = entries.slice(0, 50);
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        items,
        total: entries.length,
        page: 1,
        page_size: 50,
        pages: 1,
      }),
    });
    return;
  }

  if (method === "GET" && path === "/notifications") {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        items: state.notifications,
        total: state.notifications.length,
        unread_count: 0,
      }),
    });
    return;
  }

  await route.fulfill({
    status: 404,
    contentType: "application/json",
    body: JSON.stringify({
      error: { code: "NOT_FOUND", message: `Unmocked route: ${method} ${path}` },
    }),
  });
}

/** Install in-memory API mocks for Platform Admin E2E (no live backend required). */
export async function installPlatformAdminMocks(page: Page) {
  const state = createInitialState();

  await page.route(`${AUTHENTIK_BASE}/application/o/token/`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ access_token: "e2e-test-access-token" }),
    });
  });

  await page.route((url) => url.pathname.includes("/api/v1/"), (route) =>
    handleApiRoute(state, route),
  );

  return state;
}
