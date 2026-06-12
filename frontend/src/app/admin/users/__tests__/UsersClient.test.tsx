import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactElement } from "react";
import { UsersClient } from "../UsersClient";

vi.mock("next-intl", () => import("@/test/mocks/next-intl"));

const mockAuth = vi.fn<() => { mounted: boolean; token: string | null }>(() => ({
  mounted: true,
  token: "test-token",
}));
vi.mock("@/hooks/use-client-auth", () => ({
  useClientAuth: () => mockAuth(),
}));

const listMock = vi.fn();
const suspendMock = vi.fn();
vi.mock("@/lib/api", () => ({
  adminUsersApi: {
    list: (...a: unknown[]) => listMock(...a),
    suspend: (...a: unknown[]) => suspendMock(...a),
    reactivate: vi.fn(),
    deactivate: vi.fn(),
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
  listMock.mockResolvedValue([
    {
      id: "u1",
      email: "teacher@test.com",
      display_name: "Teacher One",
      role: "teacher",
      status: "active",
      district_id: "dist-1",
      school_id: "school-1",
      created_at: "2026-06-12T00:00:00Z",
    },
  ]);
});

describe("UsersClient", () => {
  it("renders user list and suspends a user", async () => {
    const user = userEvent.setup();
    suspendMock.mockResolvedValue({
      id: "u1",
      status: "suspended",
    });

    renderWithClient(<UsersClient />);

    await waitFor(() => expect(screen.getByText("Teacher One")).toBeInTheDocument());

    await user.click(screen.getByRole("button", { name: "actions.suspend" }));
    await user.click(screen.getByRole("button", { name: "confirm.suspend.confirm" }));

    await waitFor(() => expect(suspendMock).toHaveBeenCalledWith("test-token", "u1"));
  });
});
