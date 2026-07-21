/**
 * Phase 1/3 — real-backend admin create contract (E2E @smoke @real).
 *
 * Hits the live FastAPI process with the same payloads the UI sends after Phase 2.
 * No route mocking on create paths — requires REAL_BACKEND_URL and auth token.
 */
import { test, expect } from "@playwright/test";
import {
  EXAM_FRAMEWORK_CREATE_FROM_UI,
  EXAM_SYLLABUS_CREATE_FROM_UI,
  SUBJECT_CREATE_FROM_UI,
  SUBSCRIPTION_TIER_CREATE_FROM_UI,
} from "../src/lib/api/__tests__/fixtures/frontend-payloads";

const API_BASE = process.env.REAL_BACKEND_URL ?? "http://localhost:8000/api/v1";
const ADMIN_TOKEN = process.env.TEST_PLATFORM_ADMIN_TOKEN ?? "";
// Subjects are school-scoped (Coordinator-and-above); a coordinator token carries
// the school_id claim the endpoint requires, so it gets its own gate.
const COORDINATOR_TOKEN = process.env.TEST_COORDINATOR_TOKEN ?? "";

async function apiReachable(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/health`);
    return res.ok;
  } catch {
    return false;
  }
}

test.describe("Admin create — real backend contract @smoke @real", () => {
  test.beforeEach(async () => {
    test.skip(!(await apiReachable()), `API not reachable at ${API_BASE}`);
    test.skip(!ADMIN_TOKEN, "TEST_PLATFORM_ADMIN_TOKEN is required for @real create tests");
  });

  test("POST /admin/exam-syllabi accepts UI payload", async ({ request }) => {
    const response = await request.post(`${API_BASE}/admin/exam-syllabi`, {
      headers: {
        // T-245 removed AuthMiddleware's Bearer-header fallback — cookie-only now
        // (ARCH §6.6/§6.17). Starlette parses `Cookie` regardless of client, so a
        // raw APIRequestContext call authenticates the same way a browser would.
        Cookie: `iqbalai_access=${ADMIN_TOKEN}`,
        "Content-Type": "application/json",
      },
      data: EXAM_SYLLABUS_CREATE_FROM_UI,
    });

    expect(response.status(), await response.text()).toBe(201);
    const body = await response.json();
    expect(body.data).toBeTruthy();
    expect(body.data.name).toBe(EXAM_SYLLABUS_CREATE_FROM_UI.name);
    expect(body.data.exam_board).toBe(EXAM_SYLLABUS_CREATE_FROM_UI.exam_board);
  });

  test("POST /exam-frameworks accepts UI payload", async ({ request }) => {
    const name = `${EXAM_FRAMEWORK_CREATE_FROM_UI.name} ${Date.now()}`;

    const response = await request.post(`${API_BASE}/exam-frameworks/`, {
      headers: {
        // T-245 removed AuthMiddleware's Bearer-header fallback — cookie-only now
        // (ARCH §6.6/§6.17). Starlette parses `Cookie` regardless of client, so a
        // raw APIRequestContext call authenticates the same way a browser would.
        Cookie: `iqbalai_access=${ADMIN_TOKEN}`,
        "Content-Type": "application/json",
      },
      data: { ...EXAM_FRAMEWORK_CREATE_FROM_UI, name },
    });

    expect(response.status(), await response.text()).toBe(201);
    const body = await response.json();
    expect(body.data).toBeTruthy();
    expect(body.data.name).toBe(name);
    // New definitions always land in DRAFT (service create_framework).
    expect(body.data.status).toBe("draft");

    // T-093: the DRAFT framework can be handed to the AI research pipeline — the
    // trigger is accepted (202) and returns a RUNNING job.
    const research = await request.post(`${API_BASE}/exam-frameworks/${body.data.id}/research`, {
      headers: { Cookie: `iqbalai_access=${ADMIN_TOKEN}` },
    });
    expect(research.status(), await research.text()).toBe(202);
    const researchBody = await research.json();
    expect(researchBody.data.framework_id).toBe(body.data.id);
    expect(researchBody.data.status).toBe("running");
  });

  test("POST /admin/subscription-tiers accepts UI payload", async ({ request }) => {
    const slug = `${SUBSCRIPTION_TIER_CREATE_FROM_UI.slug}-${Date.now()}`;

    const response = await request.post(`${API_BASE}/admin/subscription-tiers`, {
      headers: {
        // T-245 removed AuthMiddleware's Bearer-header fallback — cookie-only now
        // (ARCH §6.6/§6.17). Starlette parses `Cookie` regardless of client, so a
        // raw APIRequestContext call authenticates the same way a browser would.
        Cookie: `iqbalai_access=${ADMIN_TOKEN}`,
        "Content-Type": "application/json",
      },
      data: { ...SUBSCRIPTION_TIER_CREATE_FROM_UI, slug },
    });

    expect(response.status(), await response.text()).toBe(201);
    const body = await response.json();
    expect(body.data).toBeTruthy();
    expect(body.data.slug).toBe(slug);
    expect(body.data.applies_to).toBe(SUBSCRIPTION_TIER_CREATE_FROM_UI.applies_to);
  });
});

test.describe("Coordinator create — real backend contract @smoke @real", () => {
  test.beforeEach(async () => {
    test.skip(!(await apiReachable()), `API not reachable at ${API_BASE}`);
    test.skip(!COORDINATOR_TOKEN, "TEST_COORDINATOR_TOKEN is required for @real subject create");
  });

  test("POST /subjects accepts UI payload", async ({ request }) => {
    const name = `${SUBJECT_CREATE_FROM_UI.name}-${Date.now()}`;

    const response = await request.post(`${API_BASE}/subjects/`, {
      headers: {
        Cookie: `iqbalai_access=${COORDINATOR_TOKEN}`,
        "Content-Type": "application/json",
      },
      data: { ...SUBJECT_CREATE_FROM_UI, name },
    });

    expect(response.status(), await response.text()).toBe(201);
    const body = await response.json();
    expect(body.data).toBeTruthy();
    expect(body.data.name).toBe(name);
    expect(body.data.status).toBe("active");
  });
});
