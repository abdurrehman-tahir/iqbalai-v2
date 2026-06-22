import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NextIntlClientProvider } from "next-intl";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { IndependentTeacherOnboardingClient } from "../IndependentTeacherOnboardingClient";
import en from "../../../../../../messages/en/common.json";

const completeProfileMock = vi.fn().mockResolvedValue({
  state: "ready_to_use",
  profile_complete: true,
  ready_to_use: true,
  can_create_content: true,
  profile: {
    user_id: "user-1",
    name: "Indie Teacher",
    language_preference: "en",
    profile_completed_at: "2026-06-22T00:00:00Z",
  },
});

vi.mock("@/hooks/use-client-auth", () => ({
  useClientAuth: () => ({ mounted: true, token: "test-token" }),
}));

vi.mock("@/lib/api", () => ({
  independentTeacherOnboardingApi: {
    completeProfile: (...args: unknown[]) => completeProfileMock(...args),
  },
  ApiError: class ApiError extends Error {},
}));

const mockReplace = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mockReplace }),
}));

function renderWithProviders() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <NextIntlClientProvider locale="en" messages={en}>
      <QueryClientProvider client={qc}>
        <IndependentTeacherOnboardingClient />
      </QueryClientProvider>
    </NextIntlClientProvider>,
  );
}

describe("IndependentTeacherOnboardingClient (T-070)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders minimal profile form", () => {
    renderWithProviders();
    expect(screen.getByText(/Welcome — complete your profile/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Full name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Preferred language/i)).toBeInTheDocument();
    expect(screen.queryByText(/capacity/i)).not.toBeInTheDocument();
  });

  it("submits profile and redirects to dashboard", async () => {
    const user = userEvent.setup();
    renderWithProviders();
    await user.type(screen.getByLabelText(/Full name/i), "Indie Teacher");
    await user.click(screen.getByRole("button", { name: /Save profile and continue/i }));
    await waitFor(() => expect(completeProfileMock).toHaveBeenCalled());
    await waitFor(() => expect(mockReplace).toHaveBeenCalledWith("/independent/teacher"));
  });
});
