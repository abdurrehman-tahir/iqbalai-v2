import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactElement } from "react";
import { AcademicSessionHeader } from "../AcademicSessionHeader";

vi.mock("next-intl", () => import("@/test/mocks/next-intl"));

const mockAuth = vi.fn<() => { mounted: boolean; token: string | null }>(() => ({
  mounted: true,
  token: "test-token",
}));
vi.mock("@/hooks/use-client-auth", () => ({
  useClientAuth: () => mockAuth(),
}));

const getActiveMock = vi.fn();
const listMock = vi.fn();
const createMock = vi.fn();
const activateMock = vi.fn();

vi.mock("@/lib/api", () => ({
  ApiError: class ApiError extends Error {
    constructor(
      public status: number,
      public code: string,
      message: string
    ) {
      super(message);
    }
  },
  academicSessionsApi: {
    getActive: (...a: unknown[]) => getActiveMock(...a),
    list: (...a: unknown[]) => listMock(...a),
    create: (...a: unknown[]) => createMock(...a),
    activate: (...a: unknown[]) => activateMock(...a),
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
  mockAuth.mockReturnValue({ mounted: true, token: "test-token" });
  getActiveMock.mockResolvedValue({ label: null, session: null });
  listMock.mockResolvedValue([]);
});

describe("AcademicSessionHeader", () => {
  it("shows no active session when none set", async () => {
    renderWithClient(<AcademicSessionHeader />);
    await waitFor(() => {
      expect(screen.getByText("no_active")).toBeInTheDocument();
    });
  });

  it("shows active session label", async () => {
    getActiveMock.mockResolvedValue({
      label: "2025-2026",
      session: { id: "s1", label: "2025-2026", is_active: true },
    });
    renderWithClient(<AcademicSessionHeader />);
    await waitFor(() => {
      expect(screen.getByText("active_label")).toBeInTheDocument();
    });
  });

  it("opens manage modal and creates session", async () => {
    createMock.mockResolvedValue({ id: "s2", label: "2025-2026", is_active: true });
    const user = userEvent.setup();
    renderWithClient(<AcademicSessionHeader />);
    await user.click(screen.getByRole("button", { name: "manage_button" }));
    await user.type(screen.getByLabelText(/label_field/), "2025-2026");
    await user.click(screen.getByRole("button", { name: "create_and_activate" }));
    await waitFor(() => {
      expect(createMock).toHaveBeenCalledWith("test-token", {
        label: "2025-2026",
        set_active: true,
      });
    });
  });
});
