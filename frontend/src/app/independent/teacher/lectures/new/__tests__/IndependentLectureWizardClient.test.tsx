/**
 * T-125 — Independent teacher lecture wizard (Vitest + RTL).
 * Covers the four UI states (loading/error/empty/success) across the
 * form step and the generating/complete polling step.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NextIntlClientProvider } from "next-intl";
import en from "../../../../../../../messages/en/common.json";
import { IndependentLectureWizardClient } from "../IndependentLectureWizardClient";

vi.mock("@/hooks/use-client-auth", () => ({
  useClientAuth: () => ({ mounted: true, token: "tok" }),
}));

const listReferences = vi.fn();
const getDraft = vi.fn();
const upsertDraft = vi.fn();
const generate = vi.fn();
const getLecture = vi.fn();
const getParagraphs = vi.fn();

vi.mock("@/lib/api", () => ({
  independentLectureWizardApi: {
    listReferences: (...args: unknown[]) => listReferences(...args),
    getDraft: (...args: unknown[]) => getDraft(...args),
    upsertDraft: (...args: unknown[]) => upsertDraft(...args),
    generate: (...args: unknown[]) => generate(...args),
    getLecture: (...args: unknown[]) => getLecture(...args),
    getParagraphs: (...args: unknown[]) => getParagraphs(...args),
  },
  ApiError: class ApiError extends Error {
    constructor(
      public status: number,
      public code: string,
      message: string
    ) {
      super(message);
    }
  },
}));

vi.mock("@/lib/ws/independent-lecture-voice-socket", () => ({
  useIndependentLectureVoiceSession: () => ({
    status: "idle",
    turns: [],
    errorReason: null,
    unavailableNotice: null,
    startSession: vi.fn(),
    endSession: vi.fn(),
    startRecording: vi.fn(),
    stopRecording: vi.fn(),
  }),
}));

function renderWizard() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <NextIntlClientProvider locale="en" messages={en}>
        <IndependentLectureWizardClient />
      </NextIntlClientProvider>
    </QueryClientProvider>
  );
}

describe("IndependentLectureWizardClient", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getDraft.mockResolvedValue({
      id: null,
      teacher_user_id: "t-1",
      step: 1,
      data: {},
      updated_at: null,
    });
    listReferences.mockResolvedValue([{ id: "ref-1", title: "My Notes.pdf" }]);
    upsertDraft.mockResolvedValue({
      id: "draft-1",
      teacher_user_id: "t-1",
      step: 1,
      data: {},
      updated_at: "2026-08-01T00:00:00Z",
    });
  });

  it("shows the empty state when the teacher has no references yet", async () => {
    listReferences.mockResolvedValue([]);
    renderWizard();

    expect(await screen.findByRole("heading", { name: /Create a lecture/i })).toBeInTheDocument();
    expect(await screen.findByText(/haven't uploaded any private references/i)).toBeInTheDocument();
  });

  it("shows an error state with retry when references fail to load", async () => {
    listReferences.mockRejectedValue(new Error("boom"));
    const user = userEvent.setup();
    renderWizard();

    expect(
      await screen.findByRole("heading", { name: /Could not load your references/i })
    ).toBeInTheDocument();
    listReferences.mockResolvedValue([{ id: "ref-1", title: "My Notes.pdf" }]);
    await user.click(screen.getByRole("button", { name: /Retry/i }));
    expect(await screen.findByText("My Notes.pdf")).toBeInTheDocument();
  });

  it("selects a reference, generates a lecture, and polls through to completion", async () => {
    const user = userEvent.setup();
    generate.mockResolvedValue({ lecture_id: "lec-1", status: "generating", estimated_seconds: 30 });
    getLecture.mockResolvedValue({
      id: "lec-1",
      status: "ready_for_edit",
      title: "Newton's Laws",
      current_version_id: "v-1",
    });
    getParagraphs.mockResolvedValue([
      { ordinal: 1, tier: "reference", book_name: "My Notes.pdf", text: "Force equals mass times acceleration.", source_url: null },
    ]);

    renderWizard();

    const topicInput = await screen.findByLabelText(/Topic/i);
    await user.type(topicInput, "Newton's Laws");
    await user.click(await screen.findByText("My Notes.pdf"));

    await user.click(screen.getByRole("button", { name: /Generate lecture/i }));

    await waitFor(() => expect(generate).toHaveBeenCalledWith("tok", {
      topic: "Newton's Laws",
      reference_content_ids: ["ref-1"],
      teaching_mode: "auto",
    }));

    expect(await screen.findByText(/Lecture ready/i)).toBeInTheDocument();
    expect(await screen.findByText(/Force equals mass times acceleration/i)).toBeInTheDocument();
    expect(screen.getByText("Ref: My Notes.pdf")).toBeInTheDocument();
  });

  it("shows a failure state when generation fails", async () => {
    const user = userEvent.setup();
    generate.mockResolvedValue({ lecture_id: "lec-2", status: "generating", estimated_seconds: 30 });
    getLecture.mockResolvedValue({
      id: "lec-2",
      status: "failed",
      title: "Newton's Laws",
      current_version_id: null,
    });

    renderWizard();

    const topicInput = await screen.findByLabelText(/Topic/i);
    await user.type(topicInput, "Newton's Laws");
    await user.click(screen.getByRole("button", { name: /Generate lecture/i }));

    expect(await screen.findByText(/Generation failed/i)).toBeInTheDocument();
  });
});
