/**
 * Phase 1/3 — real-backend admin create contract (E2E @smoke @real).
 *
 * Hits the live FastAPI process with the same payloads the UI sends after Phase 2.
 * No route mocking on create paths — requires REAL_BACKEND_URL and auth token.
 */
import { test, expect } from "@playwright/test";
import {
  EXAM_SYLLABUS_CREATE_FROM_UI,
  SUBSCRIPTION_TIER_CREATE_FROM_UI,
} from "../src/lib/api/__tests__/fixtures/frontend-payloads";

const API_BASE = process.env.REAL_BACKEND_URL ?? "http://localhost:8000/api/v1";
const ADMIN_TOKEN = process.env.TEST_PLATFORM_ADMIN_TOKEN ?? "";

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
        Authorization: `Bearer ${ADMIN_TOKEN}`,
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

  test("POST /admin/subscription-tiers accepts UI payload", async ({ request }) => {
    const slug = `${SUBSCRIPTION_TIER_CREATE_FROM_UI.slug}-${Date.now()}`;

    const response = await request.post(`${API_BASE}/admin/subscription-tiers`, {
      headers: {
        Authorization: `Bearer ${ADMIN_TOKEN}`,
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
