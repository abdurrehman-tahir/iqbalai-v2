import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { AuditLogClient } from "../AuditLogClient";
import { renderWithQuery } from "@/test/helpers/render-admin";

vi.mock("next-intl", () => import("@/test/mocks/next-intl"));
vi.mock("@/hooks/use-client-auth", () => ({
  useClientAuth: () => ({ mounted: true, token: "tok" }),
}));

const mockList = vi.fn();
vi.mock("@/lib/api", () => ({
  auditApi: { list: (...a: unknown[]) => mockList(...a) },
}));

beforeEach(() => vi.clearAllMocks());

describe("AuditLogClient — four UI states (T-235)", () => {
  it("loading shows heading", () => {
    mockList.mockReturnValue(new Promise(() => {}));
    renderWithQuery(<AuditLogClient />);
    expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
  });

  it("error state", async () => {
    mockList.mockRejectedValue(new Error("x"));
    renderWithQuery(<AuditLogClient />);
    await waitFor(() => expect(screen.getByText("error")).toBeInTheDocument());
  });

  it("empty state", async () => {
    mockList.mockResolvedValue([]);
    renderWithQuery(<AuditLogClient />);
    await waitFor(() => expect(screen.getByText("empty.title")).toBeInTheDocument());
  });

  it("success shows audit rows", async () => {
    mockList.mockResolvedValue([
      {
        id: "a1",
        action: "tos.published",
        actor_id: "admin",
        target_type: "tos_version",
        target_id: "t1",
        metadata: {},
        created_at: "2026-06-01T00:00:00Z",
      },
    ]);
    renderWithQuery(<AuditLogClient />);
    await waitFor(() => expect(screen.getByText("tos.published")).toBeInTheDocument());
  });
});
