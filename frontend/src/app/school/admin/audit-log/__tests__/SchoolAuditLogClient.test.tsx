import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactElement } from "react";
import { SchoolAuditLogClient } from "../SchoolAuditLogClient";

vi.mock("next-intl", () => import("@/test/mocks/next-intl"));

const mockAuth = vi.fn<() => { mounted: boolean; token: string | null }>(() => ({
  mounted: true,
  token: "test-token",
}));
vi.mock("@/hooks/use-client-auth", () => ({
  useClientAuth: () => mockAuth(),
}));

const listAuditLogMock = vi.fn();
vi.mock("@/lib/api", () => ({
  schoolAdminApi: {
    listAuditLog: (...a: unknown[]) => listAuditLogMock(...a),
  },
}));

function renderWithClient(ui: ReactElement) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("SchoolAuditLogClient", () => {
  it("renders school-scoped audit entries", async () => {
    listAuditLogMock.mockResolvedValue([
      {
        id: "a1",
        action: "user.invite_sent",
        actor_id: "sa-1",
        target_type: "user_invite",
        target_id: "inv-1",
        created_at: "2026-06-12T10:00:00Z",
      },
    ]);

    renderWithClient(<SchoolAuditLogClient />);

    await waitFor(() => expect(listAuditLogMock).toHaveBeenCalledWith("test-token"));
    await waitFor(() => expect(screen.getByText("user.invite_sent")).toBeInTheDocument());
    expect(screen.getByText("showing_last")).toBeInTheDocument();
  });
});
