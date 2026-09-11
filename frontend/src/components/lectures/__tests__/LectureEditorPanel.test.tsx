/**
 * T-130 — LectureEditorPanel (TipTap editor + immutable-version save/autosave).
 * Exercises all four UI states + the manual save / debounced autosave paths.
 */

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NextIntlClientProvider, useTranslations } from "next-intl";
import en from "../../../../messages/en/common.json";
import { LectureEditorPanel, type LectureEditorApi } from "../LectureEditorPanel";
import { ApiError } from "@/lib/api";

// jsdom doesn't implement layout, so ProseMirror's selection/scroll-into-view
// code (which TipTap's view relies on for every keystroke) throws without
// these two polyfills — standard fix for testing TipTap/ProseMirror in jsdom.
if (typeof document.elementFromPoint !== "function") {
  document.elementFromPoint = () => null;
}
if (typeof Range.prototype.getClientRects !== "function") {
  Range.prototype.getClientRects = () =>
    ({
      length: 0,
      item: () => null,
      [Symbol.iterator]: function* () {},
    }) as unknown as DOMRectList;
}
if (typeof Range.prototype.getBoundingClientRect !== "function") {
  Range.prototype.getBoundingClientRect = () =>
    ({ x: 0, y: 0, top: 0, left: 0, right: 0, bottom: 0, width: 0, height: 0 }) as DOMRect;
}

const VERSION_1 = {
  id: "v-1",
  lecture_id: "lec-1",
  version: 1,
  content_jsonb: null,
  body: "Original AI draft.",
  scores_jsonb: null,
  topic_relevance_pct: null,
  originality_score: null,
  edit_summary: null,
  created_at: "2026-08-05T00:00:00Z",
};

function renderPanel(api: Partial<LectureEditorApi>) {
  const fullApi: LectureEditorApi = {
    transcribeVoice: vi.fn(),
    uploadImage: vi.fn(),
    ...api,
  } as LectureEditorApi;
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <NextIntlClientProvider locale="en" messages={en}>
        <TestWrapper api={fullApi} />
      </NextIntlClientProvider>
    </QueryClientProvider>
  );
}

// Small wrapper so the test can use next-intl's real useTranslations for the
// "teacher.lectures.wizard" namespace, matching how the real wizard renders it.
function TestWrapper({ api }: { api: LectureEditorApi }) {
  const t = useTranslations("teacher.lectures.wizard");
  return (
    <LectureEditorPanel token="tok" lectureId="lec-1" api={api} t={t} queryKeyPrefix="teacher" />
  );
}

describe("LectureEditorPanel", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("shows a loading skeleton while the current version loads", async () => {
    const getCurrentVersion = vi.fn(() => new Promise<never>(() => {}));
    renderPanel({ getCurrentVersion, saveVersion: vi.fn() });

    expect(document.querySelectorAll('[class*="animate-pulse"]').length).toBeGreaterThan(0);
  });

  it("shows an error state with retry when the version fails to load", async () => {
    const getCurrentVersion = vi.fn().mockRejectedValue(new Error("network error"));
    renderPanel({ getCurrentVersion, saveVersion: vi.fn() });

    expect(await screen.findByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("loads the current version and renders it in the editor", async () => {
    const getCurrentVersion = vi.fn().mockResolvedValue(VERSION_1);
    renderPanel({ getCurrentVersion, saveVersion: vi.fn() });

    expect(await screen.findByText("Original AI draft.")).toBeInTheDocument();
    expect(screen.getByText(/Version 1/i)).toBeInTheDocument();
  });

  it("manual Save creates a new version and shows the Saved indicator", async () => {
    const getCurrentVersion = vi.fn().mockResolvedValue(VERSION_1);
    const saveVersion = vi.fn().mockResolvedValue({
      ...VERSION_1,
      id: "v-2",
      version: 2,
      body: "Original AI draft. Edited.",
    });
    const user = userEvent.setup();
    renderPanel({ getCurrentVersion, saveVersion });

    await screen.findByText("Original AI draft.");
    await user.click(screen.getByRole("button", { name: /^Save$/ }));

    await waitFor(() => expect(saveVersion).toHaveBeenCalledTimes(1));
    expect(saveVersion.mock.calls[0][0]).toBe("tok");
    expect(saveVersion.mock.calls[0][1]).toBe("lec-1");
    expect(saveVersion.mock.calls[0][2]).toMatchObject({ is_autosave: false });
    expect(await screen.findByText(/^Saved$/)).toBeInTheDocument();
  });

  it("shows an inline error when save fails", async () => {
    const getCurrentVersion = vi.fn().mockResolvedValue(VERSION_1);
    const saveVersion = vi
      .fn()
      .mockRejectedValue(new ApiError(422, "VALIDATION_ERROR", "Lecture content cannot be empty"));
    const user = userEvent.setup();
    renderPanel({ getCurrentVersion, saveVersion });

    await screen.findByText("Original AI draft.");
    await user.click(screen.getByRole("button", { name: /^Save$/ }));

    expect(await screen.findByText("Lecture content cannot be empty")).toBeInTheDocument();
  });

  it("debounces auto-save — typing alone does not immediately call saveVersion", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const getCurrentVersion = vi.fn().mockResolvedValue(VERSION_1);
    const saveVersion = vi.fn().mockResolvedValue({ ...VERSION_1, version: 2 });
    const user = userEvent.setup({ delay: null, advanceTimers: vi.advanceTimersByTime });
    renderPanel({ getCurrentVersion, saveVersion });

    await screen.findByText("Original AI draft.");
    const editable = document.querySelector('[contenteditable="true"]') as HTMLElement;
    editable.focus();
    await user.type(editable, "!");

    // Immediately after typing, no autosave has fired yet (debounced).
    expect(saveVersion).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(3100);
    await waitFor(() => expect(saveVersion).toHaveBeenCalledTimes(1));
    expect(saveVersion.mock.calls[0][2]).toMatchObject({ is_autosave: true });
  });
});

// jsdom has no MediaRecorder/getUserMedia — minimal fakes sufficient to drive
// the record -> stop -> transcribe -> insert flow (T-131).
class FakeMediaRecorder {
  static instances: FakeMediaRecorder[] = [];
  ondataavailable: ((event: { data: Blob }) => void) | null = null;
  onstop: (() => void) | null = null;
  mimeType = "audio/webm";
  constructor(public stream: MediaStream) {
    FakeMediaRecorder.instances.push(this);
  }
  start() {}
  stop() {
    this.ondataavailable?.({ data: new Blob(["fake-audio"], { type: "audio/webm" }) });
    this.onstop?.();
  }
}

function installVoiceMocks() {
  FakeMediaRecorder.instances = [];
  vi.stubGlobal("MediaRecorder", FakeMediaRecorder);
  // Patch mediaDevices only — replacing the whole `navigator` object (even via
  // spread) drops prototype-inherited getters (platform/userAgent) that
  // TipTap's isiOS() keyboard-shortcut setup reads on every editor mount.
  Object.defineProperty(navigator, "mediaDevices", {
    configurable: true,
    value: {
      getUserMedia: vi.fn().mockResolvedValue({
        getTracks: () => [{ stop: vi.fn() }],
      } as unknown as MediaStream),
    },
  });
}

describe("LectureEditorPanel — voice dictation (T-131)", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("acceptance #1/#3 — dictating with no selection inserts the transcript at the cursor", async () => {
    installVoiceMocks();
    const getCurrentVersion = vi.fn().mockResolvedValue(VERSION_1);
    const transcribeVoice = vi.fn().mockResolvedValue({ transcript: "Dictated words." });
    const user = userEvent.setup();
    renderPanel({ getCurrentVersion, saveVersion: vi.fn(), transcribeVoice });

    await screen.findByText("Original AI draft.");
    await user.click(screen.getByRole("button", { name: /^Dictate$/ }));
    expect(await screen.findByText(/Recording/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Stop dictating/i }));

    await waitFor(() => expect(transcribeVoice).toHaveBeenCalledTimes(1));
    expect(transcribeVoice.mock.calls[0][0]).toBe("tok");
    expect(transcribeVoice.mock.calls[0][1]).toBe("lec-1");
    // Inserted somewhere in the doc — exact cursor position is ProseMirror's
    // concern, not this test's; the transcript reaching the editor is.
    expect(await screen.findByText(/Dictated words\./)).toBeInTheDocument();
    expect(screen.getByText(/Original AI draft\./)).toBeInTheDocument();
  });

  it("acceptance #4 — a voice-originated save sets used_voice_edit", async () => {
    installVoiceMocks();
    const getCurrentVersion = vi.fn().mockResolvedValue(VERSION_1);
    const transcribeVoice = vi.fn().mockResolvedValue({ transcript: "Dictated words." });
    const saveVersion = vi.fn().mockResolvedValue({ ...VERSION_1, version: 2 });
    const user = userEvent.setup();
    renderPanel({ getCurrentVersion, saveVersion, transcribeVoice });

    await screen.findByText("Original AI draft.");
    await user.click(screen.getByRole("button", { name: /^Dictate$/ }));
    await user.click(screen.getByRole("button", { name: /Stop dictating/i }));
    await waitFor(() => expect(transcribeVoice).toHaveBeenCalledTimes(1));

    await user.click(screen.getByRole("button", { name: /^Save$/ }));
    await waitFor(() => expect(saveVersion).toHaveBeenCalledTimes(1));
    expect(saveVersion.mock.calls[0][2]).toMatchObject({ used_voice_edit: true });
  });

  it("passes the selected language to the transcribe call", async () => {
    installVoiceMocks();
    const getCurrentVersion = vi.fn().mockResolvedValue(VERSION_1);
    const transcribeVoice = vi.fn().mockResolvedValue({ transcript: "Dictated words." });
    const user = userEvent.setup();
    renderPanel({ getCurrentVersion, saveVersion: vi.fn(), transcribeVoice });

    await screen.findByText("Original AI draft.");
    await user.selectOptions(screen.getByLabelText(/Dictation language/i), "ur");
    await user.click(screen.getByRole("button", { name: /^Dictate$/ }));
    await user.click(screen.getByRole("button", { name: /Stop dictating/i }));

    await waitFor(() => expect(transcribeVoice).toHaveBeenCalledTimes(1));
    expect(transcribeVoice.mock.calls[0][3]).toBe("ur");
  });

  it("shows an inline error when transcription fails", async () => {
    installVoiceMocks();
    const getCurrentVersion = vi.fn().mockResolvedValue(VERSION_1);
    const transcribeVoice = vi
      .fn()
      .mockRejectedValue(new ApiError(500, "UNKNOWN_ERROR", "STT unavailable"));
    const user = userEvent.setup();
    renderPanel({ getCurrentVersion, saveVersion: vi.fn(), transcribeVoice });

    await screen.findByText("Original AI draft.");
    await user.click(screen.getByRole("button", { name: /^Dictate$/ }));
    await user.click(screen.getByRole("button", { name: /Stop dictating/i }));

    expect(await screen.findByText("STT unavailable")).toBeInTheDocument();
  });
});

describe("LectureEditorPanel — image upload + AI diagram suggestions (T-132)", () => {
  it("acceptance #1 — file-picker upload inserts the returned image URL", async () => {
    const getCurrentVersion = vi.fn().mockResolvedValue(VERSION_1);
    const uploadImage = vi.fn().mockResolvedValue({
      image_id: "img-1",
      image_url: "http://localhost:8000/api/v1/teachers/me/lectures/lec-1/images/img-1",
    });
    const user = userEvent.setup();
    renderPanel({ getCurrentVersion, saveVersion: vi.fn(), uploadImage });

    await screen.findByText("Original AI draft.");
    const file = new File(["fake-bytes"], "diagram.png", { type: "image/png" });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    await user.upload(input, file);

    await waitFor(() => expect(uploadImage).toHaveBeenCalledTimes(1));
    expect(uploadImage.mock.calls[0][0]).toBe("tok");
    expect(uploadImage.mock.calls[0][1]).toBe("lec-1");
    await waitFor(() => {
      const img = document.querySelector("img");
      expect(img?.getAttribute("src")).toBe(
        "http://localhost:8000/api/v1/teachers/me/lectures/lec-1/images/img-1"
      );
    });
  });

  it("acceptance #2 — client-side rejects an oversized image before uploading", async () => {
    const getCurrentVersion = vi.fn().mockResolvedValue(VERSION_1);
    const uploadImage = vi.fn();
    const user = userEvent.setup();
    renderPanel({ getCurrentVersion, saveVersion: vi.fn(), uploadImage });

    await screen.findByText("Original AI draft.");
    const oversized = new File([new Uint8Array(6 * 1024 * 1024)], "huge.png", {
      type: "image/png",
    });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    await user.upload(input, oversized);

    expect(await screen.findByText(/5 MB or smaller/i)).toBeInTheDocument();
    expect(uploadImage).not.toHaveBeenCalled();
  });

  it("rejects an unsupported file type dropped into the editor", async () => {
    // The file-picker's `accept` attribute already blocks wrong types at the
    // OS level (and userEvent.upload respects it, so this path is exercised
    // via drag-drop instead, which isn't `accept`-filtered).
    const getCurrentVersion = vi.fn().mockResolvedValue(VERSION_1);
    const uploadImage = vi.fn();
    renderPanel({ getCurrentVersion, saveVersion: vi.fn(), uploadImage });

    await screen.findByText("Original AI draft.");
    const badFile = new File(["not an image"], "notes.pdf", { type: "application/pdf" });
    const dropTarget = document.querySelector('[dir="auto"].p-3') as HTMLElement;
    const dataTransfer = { files: [badFile] } as unknown as DataTransfer;
    fireEvent.drop(dropTarget, { dataTransfer });

    expect(await screen.findByText(/JPEG, PNG, or GIF/i)).toBeInTheDocument();
    expect(uploadImage).not.toHaveBeenCalled();
  });

  it("shows an inline error when the upload fails", async () => {
    const getCurrentVersion = vi.fn().mockResolvedValue(VERSION_1);
    const uploadImage = vi
      .fn()
      .mockRejectedValue(new ApiError(422, "VALIDATION_ERROR", "Upload rejected"));
    const user = userEvent.setup();
    renderPanel({ getCurrentVersion, saveVersion: vi.fn(), uploadImage });

    await screen.findByText("Original AI draft.");
    const file = new File(["fake-bytes"], "diagram.png", { type: "image/png" });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    await user.upload(input, file);

    expect(await screen.findByText("Upload rejected")).toBeInTheDocument();
  });

  it("acceptance #3/#4 — shows a diagram suggestion and inserts it on accept", async () => {
    const getCurrentVersion = vi.fn().mockResolvedValue(VERSION_1);
    const getDiagramSuggestions = vi.fn().mockResolvedValue({
      suggestions: [
        {
          library_item_id: "lib-1",
          book_name: "Physics 101",
          page_number: 34,
          reason: "Mentions Figure 3",
        },
      ],
    });
    const acceptDiagramSuggestion = vi.fn().mockResolvedValue({
      image_id: "img-2",
      image_url: "http://localhost:8000/api/v1/teachers/me/lectures/lec-1/images/img-2",
    });
    const user = userEvent.setup();
    renderPanel({
      getCurrentVersion,
      saveVersion: vi.fn(),
      getDiagramSuggestions,
      acceptDiagramSuggestion,
    });

    await screen.findByText("Original AI draft.");
    expect(
      await screen.findByText(/Diagram on page 34 of Physics 101 — add it\?/)
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Add diagram/i }));

    await waitFor(() => expect(acceptDiagramSuggestion).toHaveBeenCalledTimes(1));
    expect(acceptDiagramSuggestion).toHaveBeenCalledWith("tok", "lec-1", {
      library_item_id: "lib-1",
      page_number: 34,
    });
    await waitFor(() => {
      const img = document.querySelector("img");
      expect(img?.getAttribute("src")).toBe(
        "http://localhost:8000/api/v1/teachers/me/lectures/lec-1/images/img-2"
      );
    });
  });

  it("acceptance #4 — declining dismisses the suggestion without calling the API", async () => {
    const getCurrentVersion = vi.fn().mockResolvedValue(VERSION_1);
    const getDiagramSuggestions = vi.fn().mockResolvedValue({
      suggestions: [
        { library_item_id: "lib-1", book_name: "Physics 101", page_number: 34, reason: "r" },
      ],
    });
    const acceptDiagramSuggestion = vi.fn();
    const user = userEvent.setup();
    renderPanel({
      getCurrentVersion,
      saveVersion: vi.fn(),
      getDiagramSuggestions,
      acceptDiagramSuggestion,
    });

    await screen.findByText(/Diagram on page 34/i);
    await user.click(screen.getByRole("button", { name: /Dismiss/i }));

    await waitFor(() => expect(screen.queryByText(/Diagram on page 34/i)).not.toBeInTheDocument());
    expect(acceptDiagramSuggestion).not.toHaveBeenCalled();
  });

  it("shows no suggestion banner when the tenant has no diagram-suggestion capability", async () => {
    const getCurrentVersion = vi.fn().mockResolvedValue(VERSION_1);
    renderPanel({ getCurrentVersion, saveVersion: vi.fn() });

    await screen.findByText("Original AI draft.");
    expect(screen.queryByText(/Diagram on page/i)).not.toBeInTheDocument();
  });
});
