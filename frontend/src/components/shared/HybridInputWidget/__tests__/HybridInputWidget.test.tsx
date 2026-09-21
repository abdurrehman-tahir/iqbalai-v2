import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NextIntlClientProvider } from "next-intl";

import { HybridInputWidget } from "../HybridInputWidget";

const messages = {
  widgets: {
    hybrid_input: {
      placeholder_default: "Ask a question...",
      placeholder_highlight: "Explain: {text}",
      mic_start: "Tap to record",
      mic_stop: "Tap to stop",
      image_attach: "Attach image",
      image_remove: "Remove image",
      image_too_large: "Image too large; max 5 MB",
      image_format_unsupported: "Format not supported — use JPEG, PNG, or WEBP",
      image_max_reached: "Max {count} images per question",
      image_not_ready: "Image attach is not available yet",
      mic_permission_denied: "Permission needed to record",
      send: "Send",
      send_error: "Could not send. Please try again.",
      auto_send_countdown: "Sending in {seconds}s — tap to cancel",
      voice_unavailable: "Voice not yet available in {language}",
      voice_error: "Could not transcribe your recording. Please try again.",
    },
  },
};

vi.mock("@/hooks/use-client-auth", () => ({
  useClientAuth: () => ({ mounted: true, token: "tok" }),
}));

vi.mock("@/lib/api", () => ({
  studentVoiceApi: {
    transcribe: vi.fn(),
  },
}));

class FakeMediaRecorder {
  static instances: FakeMediaRecorder[] = [];
  state: "inactive" | "recording" = "inactive";
  ondataavailable: ((event: { data: Blob }) => void) | null = null;
  onstop: (() => void) | null = null;
  mimeType = "audio/webm";

  constructor(_stream: MediaStream) {
    FakeMediaRecorder.instances.push(this);
  }

  start(_timeslice?: number) {
    this.state = "recording";
  }

  stop() {
    this.state = "inactive";
    this.ondataavailable?.({ data: new Blob(["chunk"], { type: "audio/webm" }) });
    this.onstop?.();
  }
}

function wrap(ui: React.ReactElement) {
  return (
    <NextIntlClientProvider locale="en" messages={messages}>
      {ui}
    </NextIntlClientProvider>
  );
}

describe("HybridInputWidget", () => {
  beforeEach(() => {
    FakeMediaRecorder.instances = [];
    vi.stubGlobal("MediaRecorder", FakeMediaRecorder);
    vi.stubGlobal("navigator", {
      ...navigator,
      mediaDevices: {
        getUserMedia: vi.fn().mockResolvedValue({
          getTracks: () => [{ stop: vi.fn() }],
        }),
      },
    });
    // AudioContext optional in jsdom — silence monitor no-ops without it.
    vi.stubGlobal(
      "AudioContext",
      vi.fn(() => {
        throw new Error("no audio");
      })
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("renders text input + mic (no image button when allowImages=false)", () => {
    render(wrap(<HybridInputWidget onSubmit={vi.fn()} />));
    expect(screen.getByTestId("hybrid-input-widget")).toBeInTheDocument();
    expect(screen.getByTestId("hybrid-text-input")).toBeInTheDocument();
    expect(screen.getByTestId("hybrid-mic-button")).toBeInTheDocument();
    expect(screen.queryByTestId("hybrid-image-button")).not.toBeInTheDocument();
  });

  it("shows image attach control when allowImages is true (M-13 stub)", () => {
    render(wrap(<HybridInputWidget onSubmit={vi.fn()} allowImages />));
    expect(screen.getByTestId("hybrid-image-button")).toBeInTheDocument();
  });

  it("submits typed text via onSubmit", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(wrap(<HybridInputWidget onSubmit={onSubmit} />));

    await user.type(screen.getByTestId("hybrid-text-input"), "What is force?");
    await user.click(screen.getByTestId("hybrid-send-button"));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith({
        text: "What is force?",
        attached_images: [],
      });
    });
  });

  it("records with red pulse and live-transcribes into the input", async () => {
    const user = userEvent.setup();
    const transcribeAudio = vi.fn().mockResolvedValue({ transcript: "Newton's laws" });
    render(wrap(<HybridInputWidget onSubmit={vi.fn()} transcribeAudio={transcribeAudio} />));

    await user.click(screen.getByTestId("hybrid-mic-button"));
    await waitFor(() => {
      expect(screen.getByTestId("hybrid-mic-button")).toHaveAttribute(
        "data-recording",
        "true"
      );
    });
    expect(screen.getByTestId("hybrid-mic-pulse")).toBeInTheDocument();
    expect(screen.getByTestId("hybrid-recording-hint")).toBeInTheDocument();

    await user.click(screen.getByTestId("hybrid-mic-button"));
    await waitFor(() => {
      expect(transcribeAudio).toHaveBeenCalled();
      expect(screen.getByTestId("hybrid-text-input")).toHaveValue("Newton's laws");
    });
  });

  it("stops recording on Escape", async () => {
    const user = userEvent.setup();
    const transcribeAudio = vi.fn().mockResolvedValue({ transcript: "stopped" });
    render(wrap(<HybridInputWidget onSubmit={vi.fn()} transcribeAudio={transcribeAudio} />));

    await user.click(screen.getByTestId("hybrid-mic-button"));
    await waitFor(() =>
      expect(screen.getByTestId("hybrid-mic-button")).toHaveAttribute(
        "data-recording",
        "true"
      )
    );

    await user.keyboard("{Escape}");
    await waitFor(() => {
      expect(screen.getByTestId("hybrid-mic-button")).toHaveAttribute(
        "data-recording",
        "false"
      );
    });
  });

  it("prefills Explain text and runs auto-send countdown (T-156 hooks)", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const onAutoSendCancel = vi.fn();

    render(
      wrap(
        <HybridInputWidget
          onSubmit={onSubmit}
          initialText="Explain: gravity pulls objects down"
          autoSendCountdownSeconds={3}
          onAutoSendCancel={onAutoSendCancel}
        />
      )
    );

    expect(screen.getByTestId("hybrid-text-input")).toHaveValue(
      "Explain: gravity pulls objects down"
    );
    expect(screen.getByTestId("hybrid-auto-send-countdown")).toHaveTextContent(
      "Sending in 3s"
    );

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
    expect(screen.getByTestId("hybrid-auto-send-countdown")).toHaveTextContent(
      "Sending in 2s"
    );

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith({
        text: "Explain: gravity pulls objects down",
        attached_images: [],
      });
    });
  });

  it("cancels auto-send on keystroke", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const onAutoSendCancel = vi.fn();

    render(
      wrap(
        <HybridInputWidget
          onSubmit={onSubmit}
          initialText="Explain: friction"
          autoSendCountdownSeconds={3}
          onAutoSendCancel={onAutoSendCancel}
        />
      )
    );

    expect(screen.getByTestId("hybrid-auto-send-countdown")).toBeInTheDocument();
    await user.type(screen.getByTestId("hybrid-text-input"), " more");
    expect(onAutoSendCancel).toHaveBeenCalled();
    expect(screen.queryByTestId("hybrid-auto-send-countdown")).not.toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });
    expect(onSubmit).not.toHaveBeenCalled();
  });
});
