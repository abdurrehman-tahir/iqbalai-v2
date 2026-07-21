import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactElement } from "react";
import { SchoolsClient } from "../SchoolsClient";

vi.mock("next-intl", () => import("@/test/mocks/next-intl"));

const mockAuth = vi.fn<() => { mounted: boolean; token: string | null }>(() => ({
  mounted: true,
  token: "test-token",
}));
vi.mock("@/hooks/use-client-auth", () => ({
  useClientAuth: () => mockAuth(),
}));

// T-245: SchoolsClient reads "who am I" via useCurrentUser() (GET /auth/me),
// not sessionStorage.
vi.mock("@/hooks/use-current-user", () => ({
  useCurrentUser: () => ({
    user: {
      user_id: "u1",
      email: "da@test.com",
      role: "district_admin",
      district_id: "dist-1",
    },
    isLoading: false,
  }),
}));

const listMock = vi.fn();
const createMock = vi.fn();
const inviteMock = vi.fn();
vi.mock("@/lib/api", () => ({
  schoolsApi: {
    list: (...a: unknown[]) => listMock(...a),
    create: (...a: unknown[]) => createMock(...a),
    delete: vi.fn(),
  },
  districtsApi: { list: vi.fn() },
  adminUsersApi: {
    invite: (...a: unknown[]) => inviteMock(...a),
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
  listMock.mockResolvedValue([]);
});

describe("SchoolsClient", () => {
  it("renders empty state and creates a school", async () => {
    const user = userEvent.setup();
    createMock.mockResolvedValue({
      id: "s1",
      name: "Sample School",
      district_id: "dist-1",
      created_at: "2026-06-12T00:00:00Z",
    });

    renderWithClient(<SchoolsClient />);

    await waitFor(() => expect(screen.getByText("empty.title")).toBeInTheDocument());

    await user.click(screen.getByRole("button", { name: "add_button" }));
    await user.type(screen.getByLabelText(/modal.name_label/), "Sample School");
    await user.click(screen.getByRole("button", { name: "modal.create" }));

    await waitFor(() =>
      expect(createMock).toHaveBeenCalledWith("test-token", {
        name: "Sample School",
        district_id: "dist-1",
      }),
    );
  });

  it("opens invite modal and submits school admin invite", async () => {
    const user = userEvent.setup();
    listMock.mockResolvedValue([
      {
        id: "school-1",
        name: "Sample School",
        district_id: "dist-1",
        created_at: "2026-06-12T00:00:00Z",
      },
    ]);
    inviteMock.mockResolvedValue({
      id: "inv-1",
      email: "sa@test.com",
      display_name: "School Admin",
      invited_role: "school_admin",
      school_id: "school-1",
      status: "pending",
    });

    renderWithClient(<SchoolsClient />);

    await waitFor(() => expect(screen.getByText("Sample School")).toBeInTheDocument());

    await user.click(screen.getByRole("button", { name: "actions.invite" }));
    await user.type(screen.getByLabelText(/invite_modal.email_label/), "sa@test.com");
    await user.type(screen.getByLabelText(/invite_modal.name_label/), "School Admin");
    await user.click(screen.getByRole("button", { name: "invite_modal.send" }));

    await waitFor(() =>
      expect(inviteMock).toHaveBeenCalledWith("test-token", {
        email: "sa@test.com",
        display_name: "School Admin",
        role: "school_admin",
        school_id: "school-1",
      }),
    );
  });
});
