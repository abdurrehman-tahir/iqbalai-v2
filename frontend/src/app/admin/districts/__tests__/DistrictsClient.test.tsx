import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactElement } from "react";
import { DistrictsClient } from "../DistrictsClient";
import type { District } from "@/lib/api";

// ── Mocks ─────────────────────────────────────────────────────────────────────

vi.mock("next-intl", () => import("@/test/mocks/next-intl"));

const mockAuth = vi.fn<() => { mounted: boolean; token: string | null }>(() => ({
  mounted: true,
  token: "test-token",
}));
vi.mock("@/hooks/use-client-auth", () => ({
  useClientAuth: () => mockAuth(),
}));

const listMock = vi.fn();
const createMock = vi.fn();
const deleteMock = vi.fn();
const inviteMock = vi.fn();
vi.mock("@/lib/api", () => ({
  districtsApi: {
    list: (...a: unknown[]) => listMock(...a),
    create: (...a: unknown[]) => createMock(...a),
    delete: (...a: unknown[]) => deleteMock(...a),
  },
  adminUsersApi: {
    invite: (...a: unknown[]) => inviteMock(...a),
  },
}));

// ── Helpers ───────────────────────────────────────────────────────────────────

function renderWithClient(ui: ReactElement) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

const sampleDistrict: District = {
  id: "11111111-1111-1111-1111-111111111111",
  name: "Lahore District",
  region: "Punjab",
  language_preference: "ur",
  created_at: "2026-06-12T00:00:00Z",
};

beforeEach(() => {
  vi.clearAllMocks();
  mockAuth.mockReturnValue({ mounted: true, token: "test-token" });
});

// ── Tests: the four required UI states ──────────────────────────────────────────

describe("DistrictsClient — UI states", () => {
  it("loading: shows skeletons before auth has mounted", () => {
    mockAuth.mockReturnValue({ mounted: false, token: null });
    listMock.mockReturnValue(new Promise(() => {})); // never resolves
    const { container } = renderWithClient(<DistrictsClient />);
    expect(container.querySelectorAll('[class*="animate-pulse"]').length).toBeGreaterThan(0);
  });

  it("error: shows the error state with a retry control", async () => {
    listMock.mockRejectedValue(new Error("boom"));
    renderWithClient(<DistrictsClient />);
    await waitFor(() => expect(screen.getByText("error")).toBeInTheDocument());
    expect(screen.getByText("retry")).toBeInTheDocument();
  });

  it("empty: shows the empty state when the list is empty", async () => {
    listMock.mockResolvedValue([]);
    renderWithClient(<DistrictsClient />);
    await waitFor(() => expect(screen.getByText("empty.title")).toBeInTheDocument());
  });

  it("success: renders a row for each district", async () => {
    listMock.mockResolvedValue([sampleDistrict]);
    renderWithClient(<DistrictsClient />);
    await waitFor(() => expect(screen.getByText("Lahore District")).toBeInTheDocument());
    expect(screen.getByText("Punjab")).toBeInTheDocument();
  });
});

// ── Tests: create flow ──────────────────────────────────────────────────────────

describe("DistrictsClient — create", () => {
  it("submits the create form and calls the API", async () => {
    const user = userEvent.setup();
    listMock.mockResolvedValue([]);
    createMock.mockResolvedValue(sampleDistrict);
    renderWithClient(<DistrictsClient />);

    await waitFor(() => expect(screen.getByText("empty.title")).toBeInTheDocument());

    // Open the create modal via the header button.
    await user.click(screen.getByRole("button", { name: "add_button" }));
    await user.type(screen.getByLabelText(/modal.name_label/), "Karachi District");
    await act(async () => {
      await user.click(screen.getByRole("button", { name: "modal.create" }));
    });

    await waitFor(() =>
      expect(createMock).toHaveBeenCalledWith("test-token", {
        name: "Karachi District",
        region: "",
        language_preference: "",
      }),
    );
  });
});

describe("DistrictsClient — invite", () => {
  it("opens invite modal and submits", async () => {
    const user = userEvent.setup();
    listMock.mockResolvedValue([sampleDistrict]);
    inviteMock.mockResolvedValue({
      id: "inv-1",
      email: "da@test.com",
      display_name: "DA",
      invited_role: "district_admin",
      district_id: sampleDistrict.id,
      school_id: null,
      status: "pending",
      expires_at: "2026-06-19T00:00:00Z",
      resent_count: 0,
      created_at: "2026-06-12T00:00:00Z",
    });
    renderWithClient(<DistrictsClient />);

    await waitFor(() => expect(screen.getByText("Lahore District")).toBeInTheDocument());

    await user.click(screen.getByRole("button", { name: "actions.invite" }));
    await user.type(screen.getByLabelText(/invite_modal.email_label/), "da@test.com");
    await user.type(screen.getByLabelText(/invite_modal.name_label/), "District Admin");
    await act(async () => {
      await user.click(screen.getByRole("button", { name: "invite_modal.send" }));
    });

    await waitFor(() =>
      expect(inviteMock).toHaveBeenCalledWith("test-token", {
        email: "da@test.com",
        display_name: "District Admin",
        role: "district_admin",
        district_id: sampleDistrict.id,
      }),
    );
  });
});
