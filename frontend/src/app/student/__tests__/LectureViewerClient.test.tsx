import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NextIntlClientProvider } from "next-intl";
import { LectureViewerClient } from "../lectures/[lectureId]/LectureViewerClient";
import { StudentLecturesPanel } from "../StudentLecturesPanel";

const openViewer = vi.fn();
const listLectures = vi.fn();
const endSession = vi.fn();
const setMode = vi.fn();
const touchSession = vi.fn();
const requestAudio = vi.fn();
const getAudio = vi.fn();

vi.mock("@/lib/api", () => ({
  studentLecturesApi: {
    list: (...args: unknown[]) => listLectures(...args),
    openViewer: (...args: unknown[]) => openViewer(...args),
    endSession: (...args: unknown[]) => endSession(...args),
    setMode: (...args: unknown[]) => setMode(...args),
    touchSession: (...args: unknown[]) => touchSession(...args),
    requestAudio: (...args: unknown[]) => requestAudio(...args),
    getAudio: (...args: unknown[]) => getAudio(...args),
    downloadAudioPath: () => "/api/v1/students/me/lectures/lec-1/audio/en/download",
  },
  studentQuestionsApi: {
    list: vi.fn().mockResolvedValue([]),
    ask: vi.fn(),
    followUp: vi.fn(),
    getAnswer: vi.fn(),
    streamAnswerUrl: () => "/api/v1/students/me/lectures/lec-1/questions/q-1/answer/stream",
  },
  studentPrivacyApi: {
    getTeacherShare: vi.fn().mockResolvedValue({ teacher_activity_share: "share" }),
    setTeacherShare: vi.fn().mockResolvedValue({ teacher_activity_share: "share" }),
  },
  studentVoiceApi: {
    transcribe: vi.fn().mockResolvedValue({ transcript: "hello" }),
  },
}));

vi.mock("@/hooks/use-client-auth", () => ({
  useClientAuth: () => ({ mounted: true, token: "tok" }),
}));

vi.mock("next-intl", async () => {
  const actual = await vi.importActual<typeof import("next-intl")>("next-intl");
  return {
    ...actual,
    useLocale: () => "en",
  };
});

const messages = {
  student: {
    lectures: {
      title: "Your lectures",
      subtitle: "Published lectures you can study.",
      loading: "Loading lectures…",
      empty: "No lectures yet.",
      error: "Could not load lectures.",
      open: "Open",
    },
    lecture_viewer: {
      loading: "Opening lecture…",
      error: "Could not open this lecture.",
      back_dashboard: "Back to dashboard",
      mode_text: "Text mode",
      mode_voice: "Voice mode",
      topic_line: "Topic: {topic}",
      badge_curriculum: "[Curriculum]",
      badge_reference: "[Ref]",
      badge_reference_named: "[Ref: {book}]",
      badge_ai: "[AI Knowledge]",
      badge_web: "[Web]",
      badge_none: "[No Source]",
      voice_on: "Turn voice on",
      voice_off: "Turn voice off",
      play: "Play",
      pause: "Pause",
      seek_back: "Skip back 10 seconds",
      seek_forward: "Skip forward 10 seconds",
      speed: "Playback speed",
      download_audio: "Download audio",
      audio_preparing: "Preparing lecture audio…",
      audio_failed: "Voice audio is unavailable.",
      ask_question: "Ask about this passage",
      highlight_prompt: "Ask about the highlighted text",
      explain_prefix: "Explain: {text}",
      question_placeholder: "Ask a question…",
      cancel: "Cancel",
      close: "Close",
      answer_panel_title: "Answer",
      your_question: "Your question",
      ai_tutor: "Tutor",
      you: "You",
      answer_preparing: "Preparing answer…",
      sources: "Sources",
      follow_up_placeholder: "Ask a follow-up…",
      questions_tab: "Your questions",
      questions_empty: "No questions yet.",
      answered: "Answered",
      classification_misconception: "Likely misconception",
      classification_knowledge_gap: "Knowledge gap",
      classification_unclassified: "Question",
      privacy_share_label: "Share study questions with my teacher",
      privacy_share_help: "When off, teachers cannot see your questions.",
    },
  },
  widgets: {
    hybrid_input: {
      placeholder_default: "Ask a question...",
      placeholder_highlight: "Explain: {text}",
      mic_start: "Tap to record",
      mic_stop: "Tap to stop",
      send: "Send",
      send_error: "Could not send.",
      auto_send_countdown: "Sending in {seconds}s",
      mic_permission_denied: "Permission needed",
      voice_unavailable: "Voice unavailable",
      voice_error: "Could not transcribe",
      image_attach: "Attach",
      image_remove: "Remove",
      image_too_large: "Too large",
      image_format_unsupported: "Bad format",
      image_max_reached: "Max images",
      image_not_ready: "Not ready",
    },
  },
};

function wrap(ui: React.ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return (
    <QueryClientProvider client={client}>
      <NextIntlClientProvider locale="en" messages={messages}>
        {ui}
      </NextIntlClientProvider>
    </QueryClientProvider>
  );
}

describe("StudentLecturesPanel", () => {
  beforeEach(() => {
    listLectures.mockReset();
    listLectures.mockResolvedValue([
      {
        lecture_id: "lec-1",
        title: "Newton",
        topic: "Forces",
        current_version_id: "ver-1",
      },
    ]);
  });

  it("lists published lectures with open links", async () => {
    render(wrap(<StudentLecturesPanel />));
    expect(await screen.findByTestId("student-lectures")).toBeInTheDocument();
    expect(await screen.findByText("Newton")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open" })).toHaveAttribute(
      "href",
      "/student/lectures/lec-1"
    );
  });
});

describe("LectureViewerClient karaoke (T-154)", () => {
  beforeEach(() => {
    openViewer.mockReset();
    setMode.mockReset();
    requestAudio.mockReset();
    getAudio.mockReset();
    touchSession.mockResolvedValue({});
    setMode.mockResolvedValue({ mode: "voice" });
    openViewer.mockResolvedValue({
      lecture_id: "lec-1",
      title: "Newton's Laws",
      topic: "Forces",
      current_version_id: "ver-1",
      language: null,
      session: {
        id: "sess-1",
        lecture_id: "lec-1",
        student_user_id: "stu-1",
        tenant_type: "school",
        mode: "text",
        status: "active",
        opened_at: "2026-09-21T12:00:00Z",
        last_activity_at: "2026-09-21T12:00:00Z",
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
    });
    requestAudio.mockResolvedValue({
      id: "aud-1",
      lecture_id: "lec-1",
      lecture_version_id: "ver-1",
      language: "en",
      status: "ready",
      audio_url: "https://minio.example/audio.wav",
      duration_ms: 2000,
      alignment: [
        {
          ordinal: 0,
          paragraph_id: "p1",
          text: "Force equals mass times acceleration.",
          start_ms: 0,
          end_ms: 2000,
        },
      ],
    });
  });

  it("opens a session and renders paragraphs with source badges", async () => {
    render(wrap(<LectureViewerClient lectureId="lec-1" />));
    await waitFor(() => expect(openViewer).toHaveBeenCalledWith("tok", "lec-1", "text"));
    expect(await screen.findByTestId("lecture-viewer")).toBeInTheDocument();
    expect(screen.getByText("Newton's Laws")).toBeInTheDocument();
    expect(screen.getAllByTestId("source-badge")[0]).toHaveAttribute("data-tier", "curriculum");
  });

  it("toggles voice mode, sets session mode, and shows karaoke controls", async () => {
    render(wrap(<LectureViewerClient lectureId="lec-1" />));
    await screen.findByTestId("lecture-viewer");
    fireEvent.click(screen.getByTestId("voice-mode-toggle"));
    await waitFor(() => expect(setMode).toHaveBeenCalledWith("tok", "sess-1", "voice"));
    await waitFor(() => expect(requestAudio).toHaveBeenCalled());
    expect(await screen.findByTestId("karaoke-player")).toBeInTheDocument();
    expect(screen.getByTestId("karaoke-play-pause")).toBeInTheDocument();
    expect(screen.getByTestId("karaoke-seek-back")).toBeInTheDocument();
    expect(screen.getByTestId("karaoke-seek-forward")).toBeInTheDocument();
    expect(screen.getByTestId("karaoke-speed")).toBeInTheDocument();
    expect(screen.getByTestId("karaoke-download")).toHaveAttribute(
      "href",
      "/api/v1/students/me/lectures/lec-1/audio/en/download"
    );
  });
});
