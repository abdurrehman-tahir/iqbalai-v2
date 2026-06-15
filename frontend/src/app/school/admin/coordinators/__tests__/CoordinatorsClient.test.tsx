import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactElement } from "react";
import { CoordinatorsClient } from "../CoordinatorsClient";

vi.mock("next-intl", () => import("@/test/mocks/next-intl"));

const mockAuth = vi.fn<() => { mounted: boolean; token: string | null }>(() => ({
  mounted: true,
  token: "test-token",
}));
vi.mock("@/hooks/use-client-auth", () => ({
  useClientAuth: () => mockAuth(),
}));

vi.mock("@/lib/auth", () => ({
  getUser: () => ({
    user_id: "sa-1",
    email: "sa@test.com",
    role: "school_admin",
    school_id: "school-1",
    tos_acceptance_required: false,
    current_tos_version_id: null,
  }),
}));

const listMock = vi.fn();
const inviteMock = vi.fn();
vi.mock("@/lib/api", () => ({
  adminUsersApi: {
    list: (...a: unknown[]) => listMock(...a),
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

describe("CoordinatorsClient", () => {
  it("invites coordinator with grade scope", async () => {
    const user = userEvent.setup();
    inviteMock.mockResolvedValue({
      id: "inv-1",
      email: "coord@test.com",
      invited_role: "coordinator",
    });

    renderWithClient(<CoordinatorsClient />);

    await waitFor(() => expect(screen.getByText("empty.title")).toBeInTheDocument());

    await user.click(screen.getByRole("button", { name: "invite_button" }));
    await user.type(screen.getByLabelText(/invite_modal.email_label/), "coord@test.com");
    await user.type(screen.getByLabelText(/invite_modal.name_label/), "Coord One");
    await user.click(screen.getByRole("checkbox", { name: "Grade 9" }));
    await user.click(screen.getByRole("checkbox", { name: "Grade 10" }));
    await user.click(screen.getByRole("button", { name: "invite_modal.send" }));

    await waitFor(() =>
      expect(inviteMock).toHaveBeenCalledWith("test-token", {
        email: "coord@test.com",
        display_name: "Coord One",
        role: "coordinator",
        grade_scope: ["Grade 9", "Grade 10"],
      }),
    );
  });
});
