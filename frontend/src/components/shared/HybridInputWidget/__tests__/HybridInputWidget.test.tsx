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
      image_upload_failed: "Could not upload image. Please try again.",
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

const uploadImageMock = vi.fn();

vi.mock("@/lib/api", () => ({
  studentVoiceApi: {
    transcribe: vi.fn(),
  },
  studentQuestionImagesApi: {
    upload: uploadImageMock,
  },
}));

function makeImageFile(name = "diagram.png", type = "image/png"): File {
  return new File(["fake-image-bytes"], name, { type });
}

class FakeMediaRecorder {
  static instances: FakeMediaRecorder[] = [];
  state: "inactive" | "recording" = "inactive";
  ondataavailable: ((event: { data: Blob }) => void) | null = null;
  onstop: (() => void) | null = null;
  mimeType = "audio/webm";

  constructor(_stream: MediaStream) {
    void _stream;
    FakeMediaRecorder.instances.push(this);
  }

  start(_timeslice?: number) {
    void _timeslice;
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
    uploadImageMock.mockReset();
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

  // T-167 — image attach / remove / max3 / drag / paste.
  describe("image attach (allowImages)", () => {
    it("uploads via the file-picker input and renders a thumbnail chip", async () => {
      const user = userEvent.setup();
      uploadImageMock.mockResolvedValue({
        upload_id: "up-1",
        storage_key: "student-question-image/s/2026/01/01/up-1/diagram.png",
        mime_type: "image/png",
        size_bytes: 17,
        retention_days: 365,
      });
      render(wrap(<HybridInputWidget onSubmit={vi.fn()} allowImages />));

      const file = makeImageFile();
      const input = screen.getByTestId("hybrid-image-input");
      await user.upload(input, file);

      await waitFor(() => {
        expect(uploadImageMock).toHaveBeenCalledWith("tok", file, 0);
        expect(screen.getByTestId("hybrid-image-chip")).toBeInTheDocument();
      });
    });

    it("removes an attached image via the chip's remove button", async () => {
      const user = userEvent.setup();
      uploadImageMock.mockResolvedValue({
        upload_id: "up-1",
        storage_key: "k1",
        mime_type: "image/png",
        size_bytes: 17,
        retention_days: 365,
      });
      render(wrap(<HybridInputWidget onSubmit={vi.fn()} allowImages />));

      await user.upload(screen.getByTestId("hybrid-image-input"), makeImageFile());
      await waitFor(() => expect(screen.getByTestId("hybrid-image-chip")).toBeInTheDocument());

      await user.click(screen.getByLabelText("Remove image"));
      expect(screen.queryByTestId("hybrid-image-chip")).not.toBeInTheDocument();
    });

    it("blocks a 4th image and shows the max-reached error", async () => {
      const user = userEvent.setup();
      let n = 0;
      uploadImageMock.mockImplementation(async () => {
        n += 1;
        return {
          upload_id: `up-${n}`,
          storage_key: `k${n}`,
          mime_type: "image/png",
          size_bytes: 17,
          retention_days: 365,
        };
      });
      render(wrap(<HybridInputWidget onSubmit={vi.fn()} allowImages maxImages={3} />));

      const input = screen.getByTestId("hybrid-image-input");
      await user.upload(input, makeImageFile("a.png"));
      await user.upload(input, makeImageFile("b.png"));
      await user.upload(input, makeImageFile("c.png"));
      await waitFor(() => expect(screen.getAllByTestId("hybrid-image-chip")).toHaveLength(3));

      // 4th attach button is disabled once the cap is reached.
      expect(screen.getByTestId("hybrid-image-button")).toBeDisabled();
      expect(uploadImageMock).toHaveBeenCalledTimes(3);
    });

    it("shows image_upload_failed when the upload request rejects", async () => {
      const user = userEvent.setup();
      uploadImageMock.mockRejectedValue(new Error("network down"));
      render(wrap(<HybridInputWidget onSubmit={vi.fn()} allowImages />));

      await user.upload(screen.getByTestId("hybrid-image-input"), makeImageFile());

      await waitFor(() => {
        expect(screen.getByTestId("hybrid-error")).toHaveTextContent(
          "Could not upload image. Please try again."
        );
      });
      expect(screen.queryByTestId("hybrid-image-chip")).not.toBeInTheDocument();
    });

    it("attaches an image dropped onto the widget container", async () => {
      uploadImageMock.mockResolvedValue({
        upload_id: "up-1",
        storage_key: "k1",
        mime_type: "image/jpeg",
        size_bytes: 17,
        retention_days: 365,
      });
      render(wrap(<HybridInputWidget onSubmit={vi.fn()} allowImages />));

      const file = makeImageFile("dropped.jpg", "image/jpeg");
      const widget = screen.getByTestId("hybrid-input-widget");
      const dataTransfer = { files: [file] } as unknown as DataTransfer;

      await act(async () => {
        widget.dispatchEvent(
          Object.assign(new Event("drop", { bubbles: true, cancelable: true }), {
            dataTransfer,
          })
        );
      });

      await waitFor(() => {
        expect(uploadImageMock).toHaveBeenCalledWith("tok", file, 0);
      });
    });

    it("attaches an image pasted from the clipboard", async () => {
      uploadImageMock.mockResolvedValue({
        upload_id: "up-1",
        storage_key: "k1",
        mime_type: "image/png",
        size_bytes: 17,
        retention_days: 365,
      });
      render(wrap(<HybridInputWidget onSubmit={vi.fn()} allowImages />));

      const file = makeImageFile("pasted.png");
      const clipboardData = {
        items: [
          {
            kind: "file",
            type: "image/png",
            getAsFile: () => file,
          },
        ],
      } as unknown as DataTransfer;
      const widget = screen.getByTestId("hybrid-input-widget");

      await act(async () => {
        widget.dispatchEvent(
          Object.assign(new Event("paste", { bubbles: true, cancelable: true }), {
            clipboardData,
          })
        );
      });

      await waitFor(() => {
        expect(uploadImageMock).toHaveBeenCalledWith("tok", file, 0);
      });
    });

    it("submits with attached_images storage keys threaded to onSubmit", async () => {
      const user = userEvent.setup();
      const onSubmit = vi.fn().mockResolvedValue(undefined);
      uploadImageMock.mockResolvedValue({
        upload_id: "up-1",
        storage_key: "student-question-image/s/2026/01/01/up-1/diagram.png",
        mime_type: "image/png",
        size_bytes: 17,
        retention_days: 365,
      });
      render(wrap(<HybridInputWidget onSubmit={onSubmit} allowImages />));

      await user.upload(screen.getByTestId("hybrid-image-input"), makeImageFile());
      await waitFor(() => expect(screen.getByTestId("hybrid-image-chip")).toBeInTheDocument());

      await user.type(screen.getByTestId("hybrid-text-input"), "What is this diagram?");
      await user.click(screen.getByTestId("hybrid-send-button"));

      await waitFor(() => {
        expect(onSubmit).toHaveBeenCalledWith({
          text: "What is this diagram?",
          attached_images: [
            expect.objectContaining({
              storage_key: "student-question-image/s/2026/01/01/up-1/diagram.png",
            }),
          ],
        });
      });
    });
  });
});
