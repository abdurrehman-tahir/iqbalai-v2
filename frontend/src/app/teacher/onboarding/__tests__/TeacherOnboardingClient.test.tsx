import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NextIntlClientProvider } from "next-intl";
import { TeacherOnboardingClient } from "../TeacherOnboardingClient";
import en from "../../../../../messages/en/common.json";

vi.mock("@/hooks/use-client-auth", () => ({
  useClientAuth: () => ({ mounted: true, token: "test-token" }),
}));

vi.mock("@/lib/api", () => ({
  teacherOnboardingApi: {
    listSubjectOptions: vi.fn().mockResolvedValue([
      { id: "subj-1", school_id: "school-1", name: "Physics", language: "en", status: "active", created_at: "" },
    ]),
    completeProfile: vi.fn().mockResolvedValue({
      state: "profile_complete",
      profile_complete: true,
      ready_to_teach: false,
      assignment_count: 0,
      can_create_content: false,
      profile: null,
    }),
  },
  ApiError: class ApiError extends Error {},
}));

const mockPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mockPush, push: mockPush }),
}));

function renderWithProviders(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <NextIntlClientProvider locale="en" messages={en}>
      <QueryClientProvider client={qc}>{ui}</QueryClientProvider>
    </NextIntlClientProvider>,
  );
}

describe("TeacherOnboardingClient (T-053)", () => {
  beforeEach(() => {
    mockPush.mockClear();
  });

  it("renders the profile form with subject options", async () => {
    renderWithProviders(<TeacherOnboardingClient />);
    expect(await screen.findByText("Physics")).toBeInTheDocument();
    expect(screen.getByLabelText(/Full name/i)).toBeInTheDocument();
  });

  it("submits profile completion", async () => {
    const user = userEvent.setup();
    renderWithProviders(<TeacherOnboardingClient />);
    await screen.findByText("Physics");

    await user.type(screen.getByLabelText(/Full name/i), "Ali Khan");
    await user.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: /Save profile and continue/i }));

    await waitFor(() => expect(mockPush).toHaveBeenCalledWith("/teacher"));
  });
});
