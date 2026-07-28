import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NextIntlClientProvider } from "next-intl";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { DiagnosticTakingClient } from "../DiagnosticTakingClient";
import en from "../../../../../messages/en/common.json";

vi.mock("@/hooks/use-client-auth", () => ({
  useClientAuth: () => ({ mounted: true, token: "tok" }),
}));

const start = vi.fn();
const saveAnswers = vi.fn();
const complete = vi.fn();
const finalizeTimeout = vi.fn();

vi.mock("@/lib/api", () => ({
  diagnosticsApi: {
    start: (...args: unknown[]) => start(...args),
    saveAnswers: (...args: unknown[]) => saveAnswers(...args),
    complete: (...args: unknown[]) => complete(...args),
    finalizeTimeout: (...args: unknown[]) => finalizeTimeout(...args),
    get: vi.fn(),
  },
}));

const baseDiag = {
  id: "d1",
  tenant_type: "school" as const,
  student_user_id: "stu-1",
  subject_id: "subj-1",
  framework_id: null,
  status: "in_progress" as const,
  questions: [
    {
      id: "q1",
      prompt: "Which is a force unit?",
      choices: ["Newton", "Kilogram"],
      topic: "Newton's Laws",
    },
    {
      id: "q2",
      prompt: "Open answer about friction",
      choices: [],
      topic: "Friction",
    },
  ],
  answers: {},
  started_at: new Date().toISOString(),
  completed_at: null,
  expires_at: new Date(Date.now() + 86_400_000).toISOString(),
};

function renderClient() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <NextIntlClientProvider locale="en" messages={en}>
        <DiagnosticTakingClient
          startRequest={{
            subject_id: "subj-1",
            subject_name: "",
            grade_label: "",
            framework_name: "",
            generate: false,
            question_count: 15,
            language: "en",
          }}
        />
      </NextIntlClientProvider>
    </QueryClientProvider>,
  );
}

describe("DiagnosticTakingClient (T-105)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    start.mockResolvedValue(baseDiag);
    saveAnswers.mockImplementation(async (_t: string, _id: string, body: { answers: Record<string, string> }) => ({
      ...baseDiag,
      answers: body.answers,
    }));
    complete.mockResolvedValue({
      diagnostic: { ...baseDiag, status: "completed", answers: { q1: "Newton" } },
      focus_areas: [
        { topic: "Friction", suggestion: "Spend more time on Friction." },
      ],
      timed_out: false,
      coaching_summary: "Nice work. Coaching guidance only.",
    });
  });

  it("shows loading then question UI", async () => {
    renderClient();
    expect(screen.getByRole("status", { name: /Preparing your diagnostic/i })).toBeInTheDocument();
    expect(await screen.findByTestId("diagnostic-taking")).toBeInTheDocument();
    expect(screen.getByText(/Which is a force unit/i)).toBeInTheDocument();
  });

  it("completes with focus areas and no grade language", async () => {
    const user = userEvent.setup();
    renderClient();
    await screen.findByTestId("diagnostic-taking");
    await user.click(screen.getByRole("radio", { name: /Newton/i }));
    await user.click(screen.getByRole("button", { name: /Next/i }));
    await waitFor(() => expect(saveAnswers).toHaveBeenCalled());
    await user.click(screen.getByRole("button", { name: /Finish/i }));
    expect(await screen.findByTestId("diagnostic-results")).toBeInTheDocument();
    expect(screen.getByText(/Areas to focus on/i)).toBeInTheDocument();
    expect(screen.getByText(/Spend more time on Friction/i)).toBeInTheDocument();
    expect(screen.getByText(/never shows marks/i)).toBeInTheDocument();
    expect(screen.queryByText(/\b\d{1,3}%\b/)).not.toBeInTheDocument();
  });

  it("shows error + retry when start fails", async () => {
    start.mockRejectedValueOnce(new Error("boom"));
    renderClient();
    expect(await screen.findByRole("alert")).toHaveTextContent(/boom/i);
    expect(screen.getByRole("button", { name: /Retry/i })).toBeInTheDocument();
  });
});
