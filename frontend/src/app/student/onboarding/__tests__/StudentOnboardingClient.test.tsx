import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactElement } from "react";
import { StudentOnboardingClient } from "../StudentOnboardingClient";

vi.mock("next-intl", () => import("@/test/mocks/next-intl"));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn() }),
}));

const mockAuth = vi.fn(() => ({ mounted: true, token: "test-token" }));
vi.mock("@/hooks/use-client-auth", () => ({
  useClientAuth: () => mockAuth(),
}));

const getOnboardingMock = vi.fn();
const completeProfileMock = vi.fn();
const getTosMock = vi.fn();

vi.mock("@/lib/api", () => ({
  studentOnboardingApi: {
    getOnboarding: (...a: unknown[]) => getOnboardingMock(...a),
    completeProfileBasic: (...a: unknown[]) => completeProfileMock(...a),
    selectModes: vi.fn(),
    dismissBanner: vi.fn(),
  },
  tosApi: {
    getCurrent: (...a: unknown[]) => getTosMock(...a),
  },
  ApiError: class ApiError extends Error {
    constructor(public status: number, public code: string, message: string) {
      super(message);
    }
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
  getOnboardingMock.mockResolvedValue({
    state: "profile_basic",
    profile_basic_complete: false,
    ready_to_study: false,
    show_complete_profile_banner: false,
    profile: null,
  });
  getTosMock.mockResolvedValue({ id: "tos-1", version_number: 1 });
  completeProfileMock.mockResolvedValue({
    state: "mode_selection",
    profile_basic_complete: true,
    ready_to_study: false,
  });
});

describe("StudentOnboardingClient", () => {
  it("submits profile basics with ToS acceptance", async () => {
    const user = userEvent.setup();
    renderWithClient(<StudentOnboardingClient />);

    await waitFor(() => expect(screen.getByLabelText(/name_label/)).toBeInTheDocument());

    await user.type(screen.getByLabelText(/name_label/), "Ali Khan");
    await user.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: "profile_submit" }));

    await waitFor(() =>
      expect(completeProfileMock).toHaveBeenCalledWith("test-token", {
        display_name: "Ali Khan",
        language_preference: "en",
        tos_version_id: "tos-1",
      }),
    );
  });
});
