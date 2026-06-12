/**
 * Phase 1 — FE↔BE contract tests (A-002).
 *
 * Asserts admin UI payloads match the generated OpenAPI create schemas.
 * These fail until SyllabiClient / SubscriptionTiersClient / api/index.ts
 * are aligned with ExamSyllabusCreate and SubscriptionTierCreate.
 */
import { describe, expect, it, vi } from "vitest";

import {
  EXAM_SYLLABUS_CREATE_FROM_UI,
  SUBSCRIPTION_TIER_CREATE_FROM_UI,
} from "./fixtures/frontend-payloads";
import {
  checkOpenApiCreateContract,
  formatContractViolation,
} from "./helpers/openapi-contract";

describe("Phase 1 — FE↔BE create payload contract", () => {
  it("exam syllabus UI payload satisfies ExamSyllabusCreate", () => {
    const violation = checkOpenApiCreateContract(
      "ExamSyllabusCreate",
      EXAM_SYLLABUS_CREATE_FROM_UI,
    );
    expect(violation, violation ? formatContractViolation(violation) : undefined).toBeNull();
  });

  it("subscription tier UI payload satisfies SubscriptionTierCreate", () => {
    const violation = checkOpenApiCreateContract(
      "SubscriptionTierCreate",
      SUBSCRIPTION_TIER_CREATE_FROM_UI,
    );
    expect(violation, violation ? formatContractViolation(violation) : undefined).toBeNull();
  });
});

describe("Phase 1 — API client error envelope contract", () => {
  it("request() reads nested error.code from backend envelope", async () => {
    const body = {
      error: {
        code: "AUTHENTICATION_REQUIRED",
        message: "Bearer token required",
      },
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: () => Promise.resolve(body),
    });

    const { ApiError, authApi } = await import("@/lib/api/index");

    try {
      await authApi.postLogin("tok");
      expect.unreachable("expected ApiError");
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError);
      const apiErr = err as InstanceType<typeof ApiError>;
      expect(apiErr.code).toBe("AUTHENTICATION_REQUIRED");
      expect(apiErr.message).toBe("Bearer token required");
    }
  });
});
