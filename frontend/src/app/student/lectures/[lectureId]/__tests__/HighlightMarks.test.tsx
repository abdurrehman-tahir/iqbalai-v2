/**
 * T-185 — persisted highlights render as yellow marks on return; marks whose
 * anchor no longer maps (server sends mark=null) drop silently (flow-6 §5.5).
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NextIntlClientProvider } from "next-intl";
import type { StudentHighlightRead } from "@/lib/api";
import { LectureViewerClient } from "../LectureViewerClient";
import { marksByParagraph, segmentParagraph } from "../highlight-marks";
import enMessages from "../../../../../../messages/en/common.json";

const listHighlights = vi.fn();
const PARA = "Force equals mass times acceleration.";

vi.mock("@/lib/api", () => ({
  studentLecturesApi: {
    openViewer: vi.fn().mockResolvedValue({
      lecture_id: "lec-1",
      title: "Newton's Laws",
      topic: "Forces",
      current_version_id: "ver-2",
      language: null,
      session: {
        id: "sess-1",
        lecture_id: "lec-1",
        student_user_id: "stu-1",
        tenant_type: "school",
        mode: "text",
        status: "active",
        opened_at: "2026-10-03T12:00:00Z",
        last_activity_at: "2026-10-03T12:00:00Z",
        ended_at: null,
      },
      paragraphs: [
        {
          id: "p1",
          ordinal: 0,
          text: "Force equals mass times acceleration.",
          tier: "curriculum",
          book_name: null,
          source_url: null,
        },
      ],
    }),
    touchSession: vi.fn().mockResolvedValue({}),
    setMode: vi.fn(),
    requestAudio: vi.fn(),
    getAudio: vi.fn(),
    downloadAudioPath: () => "/x",
  },
  studentQuestionsApi: {
    list: vi.fn().mockResolvedValue([]),
    ask: vi.fn(),
    followUp: vi.fn(),
    streamAnswerUrl: () => "/x",
  },
  studentPrivacyApi: {
    getTeacherShare: vi
      .fn()
      .mockResolvedValue({ teacher_activity_share: "share" }),
    setTeacherShare: vi.fn(),
  },
  studentVoiceApi: { transcribe: vi.fn() },
  studentQuestionImagesApi: { upload: vi.fn() },
  studentHighlightsApi: {
    listForLecture: (...args: unknown[]) => listHighlights(...args),
  },
}));

vi.mock("@/hooks/use-client-auth", () => ({
  useClientAuth: () => ({ mounted: true, token: "tok" }),
}));

function highlight(
  overrides: Partial<StudentHighlightRead> = {},
): StudentHighlightRead {
  return {
    id: "h1",
    lecture_id: "lec-1",
    lecture_version_id: "ver-1",
    paragraph_ordinal: 0,
    text_range_offset: 13,
    text_range_length: 4,
    highlighted_text: "mass",
    question_id: "q1",
    concept_tag: "forces",
    tenant_type: "school",
    created_at: "2026-10-03T12:00:00Z",
    mark: { paragraph_id: "p1", offset: 13, length: 4 },
    ...overrides,
  };
}

function renderViewer(locale = "en") {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <NextIntlClientProvider locale={locale} messages={enMessages}>
        <LectureViewerClient lectureId="lec-1" />
      </NextIntlClientProvider>
    </QueryClientProvider>,
  );
}

describe("segmentParagraph", () => {
  it("splits text into plain and marked runs", () => {
    expect(
      segmentParagraph(PARA, [{ id: "h1", offset: 13, length: 4 }]),
    ).toEqual([
      { text: "Force equals ", highlightId: null },
      { text: "mass", highlightId: "h1" },
      { text: " times acceleration.", highlightId: null },
    ]);
  });

  it("returns the whole text when there are no marks", () => {
    expect(segmentParagraph(PARA, [])).toEqual([
      { text: PARA, highlightId: null },
    ]);
  });

  it("skips overlapping and out-of-range marks instead of breaking text", () => {
    const segs = segmentParagraph(PARA, [
      { id: "a", offset: 0, length: 5 },
      { id: "b", offset: 3, length: 4 }, // overlaps a
      { id: "c", offset: 500, length: 3 }, // out of range
    ]);
    expect(segs.map((s) => s.text).join("")).toBe(PARA);
    expect(segs.filter((s) => s.highlightId).map((s) => s.highlightId)).toEqual(
      ["a"],
    );
  });

  it("marksByParagraph ignores highlights whose mark was dropped", () => {
    const map = marksByParagraph([
      highlight(),
      highlight({ id: "h2", mark: null }),
    ]);
    expect(map.get("p1")).toEqual([{ id: "h1", offset: 13, length: 4 }]);
  });
});

describe("LectureViewerClient yellow marks (T-185)", () => {
  beforeEach(() => listHighlights.mockReset());

  it("restores a persisted highlight as a yellow mark on return", async () => {
    listHighlights.mockResolvedValue([highlight()]);
    renderViewer();
    const mark = await screen.findByTestId("highlight-mark");
    expect(mark).toHaveTextContent("mass");
    expect(mark).toHaveAttribute("data-highlight-id", "h1");
    expect(mark.tagName).toBe("MARK");
    expect(screen.getByTestId("lecture-paragraph-text")).toHaveTextContent(
      PARA,
    );
    expect(listHighlights).toHaveBeenCalledWith("tok", "lec-1");
  });

  it("drops the mark silently when the lecture was re-edited (mark=null)", async () => {
    listHighlights.mockResolvedValue([highlight({ mark: null })]);
    renderViewer();
    await waitFor(() => expect(listHighlights).toHaveBeenCalled());
    expect(
      await screen.findByTestId("lecture-paragraph-text"),
    ).toHaveTextContent(PARA);
    expect(screen.queryByTestId("highlight-mark")).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("lecture-viewer-error"),
    ).not.toBeInTheDocument();
  });

  it("still renders the lecture when loading highlights fails", async () => {
    // Only the first fetch fails: a persistent rejection makes TanStack Query's
    // later background refetch surface as an unhandled rejection in the test
    // runner, which is harness noise rather than component behaviour.
    listHighlights.mockResolvedValue([]);
    listHighlights.mockRejectedValueOnce(new Error("highlights unavailable"));
    renderViewer();
    await waitFor(() =>
      expect(listHighlights.mock.settledResults[0]?.type).toBe("rejected"),
    );
    expect(
      await screen.findByTestId("lecture-paragraph-text"),
    ).toHaveTextContent(PARA);
    expect(screen.queryByTestId("highlight-mark")).not.toBeInTheDocument();
  });

  it("renders no marks when the student has no highlights (empty)", async () => {
    listHighlights.mockResolvedValue([]);
    renderViewer();
    expect(
      await screen.findByTestId("lecture-paragraph-text"),
    ).toHaveTextContent(PARA);
    expect(screen.queryByTestId("highlight-mark")).not.toBeInTheDocument();
  });
});
