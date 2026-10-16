import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NextIntlClientProvider } from "next-intl";
import en from "../../../../messages/en/common.json";
import { StudyPlanPanel } from "../StudyPlanPanel";

const mocks = vi.hoisted(() => ({
  prepBookGate: vi.fn(),
  planConversationState: vi.fn(),
  getActivePlan: vi.fn(),
  googleCalendarConfig: vi.fn(),
}));

vi.mock("@/hooks/use-client-auth", () => ({
  useClientAuth: () => ({ mounted: true, token: "tok" }),
}));

vi.mock("@fullcalendar/react", () => ({
  default: () => <div data-testid="mock-fullcalendar" />,
}));
vi.mock("@fullcalendar/daygrid", () => ({ default: {} }));
vi.mock("@fullcalendar/timegrid", () => ({ default: {} }));

vi.mock("@/components/shared/HybridInputWidget", () => ({
  HybridInputWidget: () => <div data-testid="mock-hybrid" />,
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    selfStudyApi: {
      ...actual.selfStudyApi,
      prepBookGate: mocks.prepBookGate,
      planConversationState: mocks.planConversationState,
      getActivePlan: mocks.getActivePlan,
      googleCalendarConfig: mocks.googleCalendarConfig,
    },
  };
});

function wrap(ui: React.ReactElement) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <NextIntlClientProvider locale="en" messages={en}>
        {ui}
      </NextIntlClientProvider>
    </QueryClientProvider>,
  );
}

describe("StudyPlanPanel (T-213/T-215/T-217)", () => {
  beforeEach(() => {
    mocks.prepBookGate.mockReset();
    mocks.planConversationState.mockReset();
    mocks.getActivePlan.mockReset();
    mocks.googleCalendarConfig.mockReset();
    mocks.googleCalendarConfig.mockResolvedValue({ enabled: false });
    mocks.getActivePlan.mockResolvedValue({ plan: null });
  });

  it("shows exact prep-book gate message when blocked", async () => {
    mocks.prepBookGate.mockResolvedValue({
      has_prep_book: false,
      allowed: false,
      error_message: "Please upload a prep question book to generate a study plan.",
    });
    wrap(<StudyPlanPanel />);
    await waitFor(() => {
      expect(screen.getByTestId("prep-book-gate-blocked")).toHaveTextContent(
        "Please upload a prep question book to generate a study plan.",
      );
    });
    expect(screen.queryByTestId("study-plan-google")).not.toBeInTheDocument();
  });

  it("hides Google Calendar when env-gated off", async () => {
    mocks.prepBookGate.mockResolvedValue({
      has_prep_book: true,
      allowed: true,
      error_message: null,
    });
    mocks.planConversationState.mockResolvedValue({
      step: 0,
      total_steps: 5,
      question: "What exam are you preparing for?",
      answers: {},
      complete: false,
      gate_passed: true,
    });
    mocks.googleCalendarConfig.mockResolvedValue({ enabled: false });
    wrap(<StudyPlanPanel />);
    await waitFor(() => {
      expect(screen.getByTestId("study-plan-question")).toBeInTheDocument();
    });
    expect(screen.queryByTestId("study-plan-google")).not.toBeInTheDocument();
  });
});
