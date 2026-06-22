import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NextIntlClientProvider } from "next-intl";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { StudentHomeClient } from "../StudentHomeClient";
import en from "../../../../messages/en/common.json";

vi.mock("@/hooks/use-client-auth", () => ({
  useClientAuth: () => ({ mounted: true, token: "tok" }),
}));

vi.mock("@/lib/api", () => ({
  studentOnboardingApi: {
    getOnboarding: vi.fn().mockResolvedValue({
      show_complete_profile_banner: true,
      exam_date_set: false,
      profile: null,
    }),
    dismissBanner: vi.fn(),
    setExamDate: vi.fn().mockResolvedValue({
      exam_date_set: true,
      show_complete_profile_banner: false,
      profile: { exam_date: "2026-12-01" },
    }),
  },
  parentChildLinksApi: {
    listStudentPending: vi.fn().mockResolvedValue({
      pending: [{ id: "link-1", parent_name: "Parent One", status: "pending" }],
    }),
    getStudentConnections: vi.fn().mockResolvedValue({
      access_state: "LINKED",
      linked_parents: [{ id: "link-2", parent_name: "Parent Two", status: "approved" }],
      link_history: [],
    }),
    approveLinkRequest: vi.fn().mockResolvedValue({ id: "link-1", status: "approved" }),
    revokeParentLink: vi.fn().mockResolvedValue({ id: "link-2", status: "revoked" }),
  },
}));

function renderHome() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <NextIntlClientProvider locale="en" messages={en}>
        <StudentHomeClient />
      </NextIntlClientProvider>
    </QueryClientProvider>,
  );
}

describe("StudentHomeClient link requests (T-081)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows pending parent link request and approves", async () => {
    const user = userEvent.setup();
    const { parentChildLinksApi } = await import("@/lib/api");
    renderHome();

    expect(await screen.findByText(/Add your target exam date/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Target exam date/i)).toBeInTheDocument();
    expect(await screen.findByText(/Parent One wants to link/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Approve/i }));

    await waitFor(() => {
      expect(parentChildLinksApi.approveLinkRequest).toHaveBeenCalledWith("tok", "link-1");
    });
  });
});
