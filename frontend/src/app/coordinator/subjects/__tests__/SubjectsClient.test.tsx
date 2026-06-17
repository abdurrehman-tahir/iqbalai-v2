import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactElement } from "react";
import { SubjectsClient } from "../SubjectsClient";
import { ApiError, type Subject } from "@/lib/api";

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
const updateMock = vi.fn();
const archiveMock = vi.fn();
// ApiError is defined inside the factory (hoisted above this file's top-level
// code); the test imports it back so thrown instances pass `instanceof ApiError`.
vi.mock("@/lib/api", () => {
  class MockApiError extends Error {
    constructor(
      public status: number,
      public code: string,
      message: string
    ) {
      super(message);
    }
  }
  return {
    ApiError: MockApiError,
    subjectsApi: {
      list: (...a: unknown[]) => listMock(...a),
      create: (...a: unknown[]) => createMock(...a),
      update: (...a: unknown[]) => updateMock(...a),
      archive: (...a: unknown[]) => archiveMock(...a),
    },
  };
});

// ── Helpers ───────────────────────────────────────────────────────────────────

function renderWithClient(ui: ReactElement) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

const sampleSubject: Subject = {
  id: "11111111-1111-1111-1111-111111111111",
  school_id: "school-1",
  name: "Physics",
  language: "en",
  status: "active",
  created_at: "2026-06-12T00:00:00Z",
};

beforeEach(() => {
  vi.clearAllMocks();
  mockAuth.mockReturnValue({ mounted: true, token: "test-token" });
});

// ── Tests: the four required UI states ──────────────────────────────────────────

describe("SubjectsClient — UI states", () => {
  it("loading: shows skeletons before auth has mounted", () => {
    mockAuth.mockReturnValue({ mounted: false, token: null });
    listMock.mockReturnValue(new Promise(() => {})); // never resolves
    const { container } = renderWithClient(<SubjectsClient />);
    expect(container.querySelectorAll('[class*="animate-pulse"]').length).toBeGreaterThan(0);
  });

  it("error: shows the error state with a retry control", async () => {
    listMock.mockRejectedValue(new Error("boom"));
    renderWithClient(<SubjectsClient />);
    await waitFor(() => expect(screen.getByText("error")).toBeInTheDocument());
    expect(screen.getByText("retry")).toBeInTheDocument();
  });

  it("empty: shows the empty state when the list is empty", async () => {
    listMock.mockResolvedValue([]);
    renderWithClient(<SubjectsClient />);
    await waitFor(() => expect(screen.getByText("empty.title")).toBeInTheDocument());
  });

  it("success: renders a row for each subject", async () => {
    listMock.mockResolvedValue([sampleSubject]);
    renderWithClient(<SubjectsClient />);
    await waitFor(() => expect(screen.getByText("Physics")).toBeInTheDocument());
    expect(screen.getByText("status.active")).toBeInTheDocument();
  });
});

// ── Tests: create flow ──────────────────────────────────────────────────────────

describe("SubjectsClient — create", () => {
  it("submits the create form and calls the API with name + language", async () => {
    const user = userEvent.setup();
    listMock.mockResolvedValue([]);
    createMock.mockResolvedValue(sampleSubject);
    renderWithClient(<SubjectsClient />);

    await waitFor(() => expect(screen.getByText("empty.title")).toBeInTheDocument());

    await user.click(screen.getByRole("button", { name: "add_button" }));
    await user.type(screen.getByLabelText(/modal.name_label/), "Physics");
    await act(async () => {
      await user.click(screen.getByRole("button", { name: "modal.create" }));
    });

    await waitFor(() =>
      expect(createMock).toHaveBeenCalledWith("test-token", {
        name: "Physics",
        language: "en",
      })
    );
  });

  it("surfaces a duplicate (409) error in the modal", async () => {
    const user = userEvent.setup();
    listMock.mockResolvedValue([]);
    createMock.mockRejectedValue(new ApiError(409, "CONFLICT", "duplicate"));
    renderWithClient(<SubjectsClient />);

    await waitFor(() => expect(screen.getByText("empty.title")).toBeInTheDocument());

    await user.click(screen.getByRole("button", { name: "add_button" }));
    await user.type(screen.getByLabelText(/modal.name_label/), "Physics");
    await act(async () => {
      await user.click(screen.getByRole("button", { name: "modal.create" }));
    });

    await waitFor(() => expect(screen.getByText("modal.duplicate_error")).toBeInTheDocument());
  });
});

// ── Tests: archive flow ─────────────────────────────────────────────────────────

describe("SubjectsClient — archive", () => {
  it("opens the archive confirmation and calls the API", async () => {
    const user = userEvent.setup();
    listMock.mockResolvedValue([sampleSubject]);
    archiveMock.mockResolvedValue({ ...sampleSubject, status: "archived" });
    renderWithClient(<SubjectsClient />);

    await waitFor(() => expect(screen.getByText("Physics")).toBeInTheDocument());

    await user.click(screen.getByRole("button", { name: "actions.archive" }));
    await act(async () => {
      await user.click(screen.getByRole("button", { name: "archive_modal.confirm" }));
    });

    await waitFor(() => expect(archiveMock).toHaveBeenCalledWith("test-token", sampleSubject.id));
  });
});
