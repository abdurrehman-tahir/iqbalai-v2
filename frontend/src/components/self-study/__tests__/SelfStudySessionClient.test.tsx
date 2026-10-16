import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NextIntlClientProvider } from "next-intl";
import en from "../../../../messages/en/common.json";
import { SelfStudySessionClient } from "../SelfStudySessionClient";

const mocks = vi.hoisted(() => ({
  getTodayGoal: vi.fn(),
  setGoal: vi.fn(),
  listDueFlashcards: vi.fn(),
  listMaterials: vi.fn(),
  startSession: vi.fn(),
  endSession: vi.fn(),
  respondGoalAchievement: vi.fn(),
}));

vi.mock("@/hooks/use-client-auth", () => ({
  useClientAuth: () => ({ mounted: true, token: "tok" }),
}));

vi.mock("@/components/shared/HybridInputWidget", () => ({
  HybridInputWidget: ({
    onSubmit,
    placeholder,
  }: {
    onSubmit: (p: { text: string }) => Promise<void>;
    placeholder?: string;
  }) => (
    <button
      type="button"
      data-testid={
        placeholder?.toLowerCase().includes("achieve")
          ? "mock-goal-widget"
          : "mock-ask-widget"
      }
      onClick={() => void onSubmit({ text: "Master chapter 5" })}
    >
      submit
    </button>
  ),
}));

vi.mock("@fullcalendar/react", () => ({
  default: () => <div data-testid="mock-fullcalendar" />,
}));
vi.mock("@fullcalendar/daygrid", () => ({ default: {} }));
vi.mock("@fullcalendar/timegrid", () => ({ default: {} }));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    selfStudyApi: {
      ...actual.selfStudyApi,
      getTodayGoal: mocks.getTodayGoal,
      setGoal: mocks.setGoal,
      listDueFlashcards: mocks.listDueFlashcards,
      listMaterials: mocks.listMaterials,
      startSession: mocks.startSession,
      endSession: mocks.endSession,
      respondGoalAchievement: mocks.respondGoalAchievement,
      prepBookGate: vi.fn().mockResolvedValue({
        has_prep_book: false,
        allowed: false,
        error_message: "Please upload a prep question book to generate a study plan.",
      }),
      getActivePlan: vi.fn().mockResolvedValue({ plan: null }),
      googleCalendarConfig: vi.fn().mockResolvedValue({ enabled: false }),
      getReminderPreferences: vi.fn().mockResolvedValue({
        push_enabled: true,
        email_enabled: true,
        sms_enabled: true,
        timezone: "Asia/Karachi",
      }),
      getEntry: vi.fn().mockResolvedValue({
        tenant_type: "independent",
        locked_to_self_study: true,
        active_mode: "self_study",
        state: {},
        subscription_gate: {
          enforced: false,
          allowed: true,
          max_active_plans: null,
          max_monthly_uploads: null,
        },
        lecture_mode_redirect_to: null,
      }),
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

describe("SelfStudySessionClient daily goal (T-211)", () => {
  beforeEach(() => {
    mocks.getTodayGoal.mockReset();
    mocks.setGoal.mockReset();
    mocks.listDueFlashcards.mockReset();
    mocks.startSession.mockReset();
    mocks.endSession.mockReset();
    mocks.respondGoalAchievement.mockReset();
    mocks.listDueFlashcards.mockResolvedValue({
      items: [],
      schedule_computed: false,
      schedule_owner: "flow_9",
    });
    mocks.listMaterials.mockResolvedValue({ items: [] });
    mocks.getTodayGoal.mockResolvedValue({ goal: null });
  });

  it("shows empty goal state and section", async () => {
    wrap(<SelfStudySessionClient homeHref="/independent/student" />);
    await waitFor(() => {
      expect(screen.getByTestId("self-study-goal-empty")).toBeInTheDocument();
    });
    expect(screen.getByTestId("self-study-goal-section")).toBeInTheDocument();
  });

  it("displays today's goal and surfaces it on the live panel after start", async () => {
    mocks.getTodayGoal.mockResolvedValue({
      goal: {
        id: "g1",
        tenant_type: "independent",
        goal_date: "2026-10-15",
        goal_text: "Master chapter 5",
        achieved: null,
        achievement_check_pending: true,
      },
    });
    mocks.startSession.mockResolvedValue({
      id: "sess-1",
      tenant_type: "independent",
      mode: "self_study",
      status: "active",
      material_id: null,
      study_plan_id: null,
      retrieval_primary: "student_upload_chunks",
      retrieval_overlays: ["ai_knowledge"],
      reaches_flow7: false,
    });

    wrap(<SelfStudySessionClient homeHref="/independent/student" />);
    await waitFor(() => {
      expect(screen.getByTestId("self-study-goal-text")).toHaveTextContent(
        "Master chapter 5",
      );
    });
    screen.getByTestId("self-study-start-session").click();
    await waitFor(() => {
      expect(screen.getByTestId("live-feedback-daily-goal")).toHaveTextContent(
        "Master chapter 5",
      );
    });
  });
});
