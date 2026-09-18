"use client";

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NextIntlClientProvider } from "next-intl";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { QuizAttemptClient } from "../quizzes/[assignmentId]/QuizAttemptClient";
import en from "../../../../messages/en/common.json";

vi.mock("@/hooks/use-client-auth", () => ({
  useClientAuth: () => ({ mounted: true, token: "tok" }),
}));

const submitMock = vi.fn().mockResolvedValue({
  assignment_id: "asg-1",
  attempt_id: "att-1",
  score: 1,
  max_score: 1,
  status: "completed",
  questions: [
    {
      question_id: "q1",
      ordinal: 1,
      stem: "What is force?",
      selected: "A",
      correct_answer: "A",
      is_correct: true,
      source_excerpt: "Force causes acceleration.",
    },
  ],
});

vi.mock("@/lib/api", () => ({
  studentQuizzesApi: {
    get: vi.fn().mockResolvedValue({
      assignment_id: "asg-1",
      quiz_id: "quiz-1",
      lecture_id: "lec-1",
      lecture_topic: "Forces",
      status: "published",
      questions: [
        {
          id: "q1",
          ordinal: 1,
          stem: "What is force?",
          options: [
            { key: "A", text: "A push or pull" },
            { key: "B", text: "A color" },
          ],
        },
      ],
    }),
    submit: (...args: unknown[]) => submitMock(...args),
  },
}));

function renderAttempt() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <NextIntlClientProvider locale="en" messages={en}>
        <QuizAttemptClient assignmentId="asg-1" />
      </NextIntlClientProvider>
    </QueryClientProvider>,
  );
}

describe("QuizAttemptClient (T-146)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("submits answers and shows supportive results", async () => {
    const user = userEvent.setup();
    renderAttempt();

    expect(await screen.findByText(/What is force/i)).toBeInTheDocument();
    await user.click(screen.getByLabelText(/A push or pull/i));
    await user.click(screen.getByRole("button", { name: /Submit answers/i }));

    await waitFor(() => {
      expect(submitMock).toHaveBeenCalled();
    });
    expect(await screen.findByTestId("quiz-results")).toBeInTheDocument();
    expect(screen.getByText(/Score: 1 \/ 1/i)).toBeInTheDocument();
    expect(screen.getByText(/focus on what to revisit/i)).toBeInTheDocument();
  });
});
