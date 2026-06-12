import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactElement } from "react";
import { TeachersClient } from "../TeachersClient";

vi.mock("next-intl", () => import("@/test/mocks/next-intl"));

vi.mock("@/hooks/use-client-auth", () => ({
  useClientAuth: () => ({ mounted: true, token: "test-token" }),
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

describe("TeachersClient", () => {
  it("invites a teacher", async () => {
    const user = userEvent.setup();
    inviteMock.mockResolvedValue({ id: "inv-1", email: "teacher@test.com" });

    renderWithClient(<TeachersClient />);
    await waitFor(() => expect(screen.getByText("empty.title")).toBeInTheDocument());

    await user.click(screen.getByRole("button", { name: "invite_button" }));
    await user.type(screen.getByLabelText(/invite_modal.email_label/), "teacher@test.com");
    await user.type(screen.getByLabelText(/invite_modal.name_label/), "Teacher One");
    await user.click(screen.getByRole("button", { name: "invite_modal.send" }));

    await waitFor(() =>
      expect(inviteMock).toHaveBeenCalledWith("test-token", {
        email: "teacher@test.com",
        display_name: "Teacher One",
        role: "teacher",
      }),
    );
  });
});
