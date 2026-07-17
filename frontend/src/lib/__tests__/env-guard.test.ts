import { describe, it, expect, vi } from "vitest";

import { assertAuthEnv, DEPLOY_CRITICAL_AUTH_ENV_VARS } from "../env-guard";

const FULL_ENV = {
  NEXT_PUBLIC_AUTHENTIK_URL: "https://iqbalai.pk/idp",
  NEXT_PUBLIC_APP_URL: "https://iqbalai.pk",
  NEXT_PUBLIC_AUTHENTIK_CLIENT_ID: "iqbalai-frontend",
};

describe("assertAuthEnv", () => {
  it("throws in production when a deploy-critical var is missing", () => {
    const incomplete = {
      NEXT_PUBLIC_APP_URL: FULL_ENV.NEXT_PUBLIC_APP_URL,
      NEXT_PUBLIC_AUTHENTIK_CLIENT_ID: FULL_ENV.NEXT_PUBLIC_AUTHENTIK_CLIENT_ID,
    };
    expect(() => assertAuthEnv("production", incomplete)).toThrow(
      /NEXT_PUBLIC_AUTHENTIK_URL/,
    );
  });

  it("throws in production when all vars are missing", () => {
    expect(() => assertAuthEnv("production", {})).toThrow(/production/i);
  });

  it("does not throw in production when every var is set", () => {
    expect(() => assertAuthEnv("production", FULL_ENV)).not.toThrow();
  });

  it("warns (does not throw) in dev when vars are missing", () => {
    const warn = vi.fn();
    expect(() => assertAuthEnv("development", {}, warn)).not.toThrow();
    expect(warn).toHaveBeenCalledOnce();
    expect(warn.mock.calls[0]?.[0]).toMatch(/localhost/i);
  });

  it("does not warn in dev when every var is set", () => {
    const warn = vi.fn();
    assertAuthEnv("development", FULL_ENV, warn);
    expect(warn).not.toHaveBeenCalled();
  });

  it("DEPLOY_CRITICAL_AUTH_ENV_VARS lists exactly the three login-path vars", () => {
    expect(DEPLOY_CRITICAL_AUTH_ENV_VARS).toEqual([
      "NEXT_PUBLIC_AUTHENTIK_URL",
      "NEXT_PUBLIC_APP_URL",
      "NEXT_PUBLIC_AUTHENTIK_CLIENT_ID",
    ]);
  });
});
