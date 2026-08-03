/**
 * T-117 — GenerationStreamPanel (wizard Step 5's live-generation view).
 * Exercises all four UI states by mocking `useLectureGenerationStream` directly —
 * the actual WebSocket reconnect/backoff logic is covered by
 * `lecture-generation-socket.test.ts`.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NextIntlClientProvider } from "next-intl";
import en from "../../../../../../messages/en/common.json";
import { LectureWizardClient } from "../LectureWizardClient";
import type { LectureGenerationState } from "@/lib/ws/lecture-generation-socket";

vi.mock("@/hooks/use-client-auth", () => ({
  useClientAuth: () => ({ mounted: true, token: "tok" }),
}));

const mockStream = vi.fn<() => LectureGenerationState>();
vi.mock("@/lib/ws/lecture-generation-socket", () => ({
  useLectureGenerationStream: () => mockStream(),
}));

const listOfferings = vi.fn();
const listCurricula = vi.fn();
const listTopics = vi.fn();
const listReferences = vi.fn();
const getDraft = vi.fn();
const upsertDraft = vi.fn();
const getEstimate = vi.fn();
const generate = vi.fn();
const getParagraphs = vi.fn();

vi.mock("@/lib/api", () => ({
  lectureWizardApi: {
    listOfferings: (...args: unknown[]) => listOfferings(...args),
    listCurricula: (...args: unknown[]) => listCurricula(...args),
    listTopics: (...args: unknown[]) => listTopics(...args),
    listReferences: (...args: unknown[]) => listReferences(...args),
    getDraft: (...args: unknown[]) => getDraft(...args),
    upsertDraft: (...args: unknown[]) => upsertDraft(...args),
    getEstimate: (...args: unknown[]) => getEstimate(...args),
    generate: (...args: unknown[]) => generate(...args),
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

function renderAtStep5GeneratingLecture() {
  getDraft.mockResolvedValue({
    id: "draft-1",
    teacher_user_id: "t-1",
    step: 5,
    data: {
      grade_subject_offering_id: "off-1",
      topic: "Newton's Laws",
      topic_source: "tree",
      curriculum_id: "curr-1",
      reference_book_ids: [],
      include_cross_grade: false,
      teaching_mode: "auto",
      lecture_id: "lec-1",
    },
    updated_at: "2026-07-30T00:00:00Z",
  });
  listOfferings.mockResolvedValue([
    {
      id: "off-1",
      grade_id: "g-1",
      grade_name: "Grade 9",
      grade_level_ordinal: 9,
      subject_id: "s-1",
      subject_name: "Physics",
      academic_session: "2025-2026",
    },
  ]);
  listCurricula.mockResolvedValue([]);
  listReferences.mockResolvedValue([]);
  getEstimate.mockResolvedValue({
    estimated_seconds: 60,
    reference_count: 0,
    teaching_mode: "auto",
  });

  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <NextIntlClientProvider locale="en" messages={en}>
        <LectureWizardClient />
      </NextIntlClientProvider>
    </QueryClientProvider>
  );
}

describe("GenerationStreamPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows a loading skeleton while connecting with no output yet", async () => {
    mockStream.mockReturnValue({
      status: "connecting",
      text: "",
      versionId: null,
      errorReason: null,
    });
    renderAtStep5GeneratingLecture();

    expect(await screen.findByText(/Generating your lecture/i)).toBeInTheDocument();
    expect(screen.getByText(/Generating your lecture/i).closest("section")).toHaveAttribute(
      "aria-busy",
      "true"
    );
  });

  it("streams live tokens into the transcript", async () => {
    mockStream.mockReturnValue({
      status: "streaming",
      text: "Newton's first law states that...",
      versionId: null,
      errorReason: null,
    });
    renderAtStep5GeneratingLecture();

    expect(
      await screen.findByText(/Newton's first law states that/i)
    ).toBeInTheDocument();
  });

  it("shows a reconnecting notice without losing the transcript so far", async () => {
    mockStream.mockReturnValue({
      status: "reconnecting",
      text: "Newton's first law",
      versionId: null,
      errorReason: null,
    });
    renderAtStep5GeneratingLecture();

    expect(await screen.findByText(/reconnecting/i)).toBeInTheDocument();
    expect(screen.getByText(/Newton's first law/i)).toBeInTheDocument();
  });

  it("shows the ready state and source-badged paragraphs when generation completes", async () => {
    mockStream.mockReturnValue({
      status: "complete",
      text: "Newton's first law states that...",
      versionId: "ver-1",
      errorReason: null,
    });
    getParagraphs.mockResolvedValue([
      { ordinal: 0, text: "Newton's first law...", tier: "curriculum", book_name: null },
      {
        ordinal: 1,
        text: "For example, a bus braking...",
        tier: "reference",
        book_name: "Physics Today",
      },
      { ordinal: 2, text: "This extends to rotation.", tier: "ai_knowledge", book_name: null },
    ]);
    renderAtStep5GeneratingLecture();

    expect(await screen.findByText(/Lecture ready/i)).toBeInTheDocument();
    expect(await screen.findByText("Curriculum")).toBeInTheDocument();
    expect(await screen.findByText("Ref: Physics Today")).toBeInTheDocument();
    expect(await screen.findByText("AI Knowledge")).toBeInTheDocument();
    expect(screen.getByText(/For example, a bus braking/i)).toBeInTheDocument();
  });

  it("shows the Web badge for T-119 out-of-curriculum fallback paragraphs", async () => {
    mockStream.mockReturnValue({
      status: "complete",
      text: "Quantum foam is a concept...",
      versionId: "ver-1",
      errorReason: null,
    });
    getParagraphs.mockResolvedValue([
      { ordinal: 0, text: "Quantum foam is a concept...", tier: "web", book_name: null },
    ]);
    renderAtStep5GeneratingLecture();

    expect(await screen.findByText("Web")).toBeInTheDocument();
  });

  it("shows a paragraphs error state with retry when the read fails", async () => {
    mockStream.mockReturnValue({
      status: "complete",
      text: "Newton's first law...",
      versionId: "ver-1",
      errorReason: null,
    });
    getParagraphs.mockRejectedValue(new Error("network error"));
    renderAtStep5GeneratingLecture();

    expect(
      await screen.findByRole("heading", { name: /Could not load the lecture content/i })
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("shows an error state when generation fails", async () => {
    mockStream.mockReturnValue({
      status: "error",
      text: "",
      versionId: null,
      errorReason: "timed_out",
    });
    renderAtStep5GeneratingLecture();

    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(await screen.findByText(/Generation failed/i)).toBeInTheDocument();
    expect(screen.getByText(/timed out/i)).toBeInTheDocument();
  });
});
