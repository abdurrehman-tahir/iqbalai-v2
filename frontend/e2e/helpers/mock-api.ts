import type { Page, Route } from "@playwright/test";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
const AUTHENTIK_BASE = process.env.NEXT_PUBLIC_AUTHENTIK_URL ?? "http://localhost:9000";

interface Syllabus {
  id: string;
  name: string;
  description: string | null;
  version: number;
  is_active: boolean;
}

interface SubscriptionTier {
  id: string;
  name: string;
  pricing_monthly_pkr: number;
  caps: Record<string, unknown>;
  applies_to_role: string;
  is_active: boolean;
}

interface Persona {
  id: string;
  name: string;
  description: string | null;
  system_prompt: string;
  is_custom: boolean;
  is_active: boolean;
}

interface AuditEntry {
  id: string;
  action: string;
  actor_id: string;
  target_type: string;
  target_id: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
}

interface District {
  id: string;
  name: string;
  region: string | null;
  language_preference: string | null;
  created_at: string;
}

interface MockState {
  userId: string;
  email: string;
  tosAccepted: boolean;
  tosVersionId: string;
  tosContent: string;
  districts: District[];
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
    target_type: targetType,
    target_id: targetId,
    metadata,
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
    districts: [],
    syllabi: [],
    tiers: [],
    personas: [
      {
        id: "persona-1",
        name: "Strict",
        description: null,
        system_prompt: "You are a strict teacher.",
        is_custom: false,
        is_active: true,
      },
      {
        id: "persona-2",
        name: "Friendly Tutor",
        description: null,
        system_prompt: "You are a friendly tutor.",
        is_custom: false,
        is_active: true,
      },
      {
        id: "persona-3",
        name: "Storyteller",
        description: null,
        system_prompt: "You teach through stories.",
        is_custom: false,
        is_active: true,
      },
      {
        id: "persona-4",
        name: "Exam Coach",
        description: null,
        system_prompt: "You focus on exam preparation.",
        is_custom: false,
        is_active: true,
      },
      {
        id: "persona-5",
        name: "Custom",
        description: "Per-student learned persona slot",
        system_prompt: "Managed by platform batch job.",
        is_custom: true,
        is_active: true,
      },
    ],
    auditLog: [
      {
        id: "audit-bootstrap",
        action: "user.created",
        actor_id: "system",
        target_type: "user",
        target_id: "user-platform-admin-1",
        metadata: { role: "platform_admin" },
        created_at: new Date().toISOString(),
      },
    ],
    notifications: [],
    library: [],
    tosVersions: [
      {
        id: tosVersionId,
        version: 1,
        content: "IqbalAI Platform Terms of Service (E2E fixture).\n\nScroll to the bottom to accept.",
        effective_at: new Date().toISOString(),
      },
    ],
    disclaimerVersions: [
      {
        id: "disclaimer-v1",
        version: 1,
        content: "AI predictions are indicative only.",
        effective_at: new Date().toISOString(),
      },
    ],
  };
}

async function handleApiRoute(state: MockState, route: Route) {
  const request = route.request();
  const url = new URL(request.url());
  const path = url.pathname.replace("/api/v1", "");
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
        version: 1,
        content: state.tosContent,
        effective_at: new Date().toISOString(),
      }),
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

  if (method === "GET" && path === "/admin/districts/") {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: envelope(state.districts),
    });
    return;
  }

  if (method === "POST" && path === "/admin/districts/") {
    const body = (await request.postDataJSON()) as {
      name: string;
      region?: string;
      language_preference?: string;
    };
    const district: District = {
      id: `district-${state.districts.length + 1}`,
      name: body.name,
      region: body.region ?? null,
      language_preference: body.language_preference ?? null,
      created_at: new Date().toISOString(),
    };
    state.districts.push(district);
    audit(state, "district.created", "district", district.id, { name: body.name });
    await route.fulfill({
      status: 201,
      contentType: "application/json",
      body: envelope(district),
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
    const body = (await request.postDataJSON()) as { name: string; description?: string };
    const syllabus: Syllabus = {
      id: `syllabus-${state.syllabi.length + 1}`,
      name: body.name,
      description: body.description ?? null,
      version: 1,
      is_active: true,
    };
    state.syllabi.push(syllabus);
    audit(state, "exam_syllabus.created", "exam_syllabus", syllabus.id, { name: body.name });
    await route.fulfill({
      status: 200,
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

  if (method === "GET" && path === "/admin/subscription-tiers") {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: envelope(state.tiers),
    });
    return;
  }

  if (method === "POST" && path === "/admin/subscription-tiers") {
    const body = (await request.postDataJSON()) as Omit<SubscriptionTier, "id">;
    const tier: SubscriptionTier = {
      id: `tier-${state.tiers.length + 1}`,
      ...body,
    };
    state.tiers.push(tier);
    audit(state, "subscription_tier.created", "subscription_tier", tier.id, { name: body.name });
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: envelope(tier),
    });
    return;
  }

  if (method === "GET" && path === "/admin/tos") {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: envelope(state.tosVersions),
    });
    return;
  }

  if (method === "GET" && path === "/admin/disclaimer") {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: envelope(state.disclaimerVersions),
    });
    return;
  }

  if (method === "GET" && path === "/admin/library") {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: envelope(state.library),
    });
    return;
  }

  if (method === "GET" && path === "/admin/audit-log") {
    const actor = url.searchParams.get("actor");
    const action = url.searchParams.get("action");
    let entries = state.auditLog;
    if (actor) entries = entries.filter((e) => e.actor_id.includes(actor));
    if (action) entries = entries.filter((e) => e.action.includes(action));
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: envelope(entries.slice(0, 50)),
    });
    return;
  }

  if (method === "GET" && path === "/notifications") {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: envelope(state.notifications),
    });
    return;
  }

  await route.fulfill({
    status: 404,
    contentType: "application/json",
    body: JSON.stringify({ code: "NOT_FOUND", message: `Unmocked route: ${method} ${path}` }),
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

  await page.route(`${API_BASE}/**`, (route) => handleApiRoute(state, route));

  return state;
}
