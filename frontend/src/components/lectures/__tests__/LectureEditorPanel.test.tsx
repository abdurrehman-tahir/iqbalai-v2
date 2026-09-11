/**
 * T-130 — LectureEditorPanel (TipTap editor + immutable-version save/autosave).
 * Exercises all four UI states + the manual save / debounced autosave paths.
 */

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
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

function renderPanel(api: LectureEditorApi) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <NextIntlClientProvider locale="en" messages={en}>
        <TestWrapper api={api} />
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
