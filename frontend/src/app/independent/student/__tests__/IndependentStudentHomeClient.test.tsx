import { render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { IndependentStudentHomeClient } from "../IndependentStudentHomeClient";
import en from "../../../../../messages/en/common.json";

vi.mock("@/hooks/use-client-auth", () => ({
  useClientAuth: () => ({ mounted: true, token: "tok" }),
}));

vi.mock("@/lib/api", () => ({
  independentStudentOnboardingApi: {
    getOnboarding: vi.fn().mockResolvedValue({
      ready_to_study: true,
      exam_date_passed: false,
      self_study_only: true,
      profile: null,
    }),
    setExamDate: vi.fn(),
  },
  selfStudyApi: {
    getEntry: vi.fn().mockResolvedValue({
      tenant_type: "independent",
      locked_to_self_study: true,
      active_mode: "self_study",
      state: { last_goal_id: null, last_material_id: null, last_plan_view: null },
      subscription_gate: {
        enforced: false,
        allowed: true,
        max_active_plans: null,
        max_monthly_uploads: null,
      },
      lecture_mode_redirect_to: "/independent/student",
    }),
    patchState: vi.fn(),
  },
}));

function renderHome() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <NextIntlClientProvider locale="en" messages={en}>
        <IndependentStudentHomeClient />
      </NextIntlClientProvider>
    </QueryClientProvider>,
  );
}

describe("IndependentStudentHomeClient (T-209)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows Self-Study layout only (no Lecture section)", async () => {
    renderHome();
    expect(await screen.findByTestId("independent-self-study-dashboard")).toBeInTheDocument();
    expect(screen.getByTestId("self-study-section")).toBeInTheDocument();
    expect(screen.queryByTestId("lecture-section")).not.toBeInTheDocument();
    expect(screen.getByText(/no lecture mode switcher/i)).toBeInTheDocument();
    expect(await screen.findByTestId("self-study-subscription-gate")).toBeInTheDocument();
  });
});
