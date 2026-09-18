/**
 * T-121 — useLectureVoiceSession: WS message handling, mic capture, TTS playback.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import { useLectureVoiceSession } from "../lecture-voice-socket";

vi.mock("@/lib/api", () => ({
  API_BASE: "http://localhost:8000/api/v1",
}));

class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  static OPEN = 1;
  url: string;
  sent: string[] = [];
  readyState = 1;
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;

  constructor(url: string) {
    this.url = url;
    FakeWebSocket.instances.push(this);
  }

  send(data: string): void {
    this.sent.push(data);
  }

  close(): void {
    this.readyState = 3;
    this.onclose?.();
  }

  emitOpen(): void {
    this.onopen?.();
  }

  emitMessage(payload: unknown): void {
    this.onmessage?.({ data: JSON.stringify(payload) });
  }
}

function envelope(type: string, data: Record<string, unknown> = {}) {
  return { type, id: "m-1", data, meta: { timestamp: "2026-08-04T00:00:00Z", request_id: null } };
}

class FakeMediaRecorder {
  static instances: FakeMediaRecorder[] = [];
  ondataavailable: ((event: { data: Blob }) => void) | null = null;
  started = false;
  stopped = false;

  constructor(public stream: MediaStream) {
    FakeMediaRecorder.instances.push(this);
  }

  start(): void {
    this.started = true;
  }

  stop(): void {
    this.stopped = true;
  }
}

function makeFakeStream(): MediaStream {
  const track = { stop: vi.fn() };
  return { getTracks: () => [track] } as unknown as MediaStream;
}

beforeEach(() => {
  FakeWebSocket.instances = [];
  FakeMediaRecorder.instances = [];
  vi.stubGlobal("WebSocket", FakeWebSocket);
  vi.stubGlobal("MediaRecorder", FakeMediaRecorder);
  vi.stubGlobal("navigator", {
    mediaDevices: { getUserMedia: vi.fn().mockResolvedValue(makeFakeStream()) },
  });
  const playMock = vi.fn().mockResolvedValue(undefined);
  vi.stubGlobal(
    "Audio",
    vi.fn().mockImplementation(() => ({ play: playMock, set onended(_fn: unknown) {} }))
  );
  vi.stubGlobal("URL", { createObjectURL: vi.fn(() => "blob:fake"), revokeObjectURL: vi.fn() });
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("useLectureVoiceSession", () => {
  it("does not connect until startSession is called", () => {
    renderHook(() => useLectureVoiceSession("lec-1", "en"));
    expect(FakeWebSocket.instances).toHaveLength(0);
  });

  it("connects to the derived voice WS URL with the language query param", () => {
    const { result } = renderHook(() => useLectureVoiceSession("lec-1", "en"));
    act(() => result.current.startSession());

    expect(FakeWebSocket.instances).toHaveLength(1);
    expect(FakeWebSocket.instances[0].url).toBe(
      "ws://localhost:8000/ws/v1/lectures/lec-1/voice?language=en"
    );
    expect(result.current.status).toBe("connecting");
  });

  it("transitions to ready on `connected`", () => {
    const { result } = renderHook(() => useLectureVoiceSession("lec-1", "en"));
    act(() => result.current.startSession());
    const ws = FakeWebSocket.instances[0];

    act(() => ws.emitMessage(envelope("connected", { session_id: "vs-1" })));

    expect(result.current.status).toBe("ready");
  });

  it("records audio, sends base64 chunks, and ends the turn on stop", async () => {
    const { result } = renderHook(() => useLectureVoiceSession("lec-1", "en"));
    act(() => result.current.startSession());
    const ws = FakeWebSocket.instances[0];
    act(() => ws.emitMessage(envelope("connected", {})));

    await act(async () => {
      await result.current.startRecording();
    });
    expect(result.current.status).toBe("recording");
    const recorder = FakeMediaRecorder.instances[0];
    expect(recorder.started).toBe(true);

    const chunkBlob = new Blob(["fake-audio"], { type: "audio/webm" });
    act(() => {
      recorder.ondataavailable?.({ data: chunkBlob });
    });

    // FileReader.readAsDataURL's onloadend fires as a macrotask in jsdom, on a task
    // source whose timing relative to setTimeout isn't guaranteed — poll with real
    // timers instead of a single fixed-delay tick, which flakes under system load.
    await waitFor(() => {
      const chunkMessages = ws.sent.map((s) => JSON.parse(s)).filter((m) => m.type === "voice_audio_chunk");
      expect(chunkMessages.length).toBeGreaterThan(0);
    });
    const chunkMessages = ws.sent.map((s) => JSON.parse(s)).filter((m) => m.type === "voice_audio_chunk");
    expect(typeof chunkMessages[0].data.audio_base64).toBe("string");

    act(() => result.current.stopRecording());
    expect(result.current.status).toBe("processing");
    expect(recorder.stopped).toBe(true);
    const turnEndMessages = ws.sent.map((s) => JSON.parse(s)).filter((m) => m.type === "voice_turn_end");
    expect(turnEndMessages).toHaveLength(1);
  });

  it("appends a turn on voice_transcript and marks it edited on lecture_draft_updated", () => {
    const { result } = renderHook(() => useLectureVoiceSession("lec-1", "en"));
    act(() => result.current.startSession());
    const ws = FakeWebSocket.instances[0];
    act(() => ws.emitMessage(envelope("connected", {})));

    act(() =>
      ws.emitMessage(
        envelope("voice_transcript", {
          transcript: "add an example",
          confirmation: "Adding an example.",
        })
      )
    );
    expect(result.current.turns).toHaveLength(1);
    expect(result.current.turns[0].hadDraftEdit).toBe(false);

    act(() => ws.emitMessage(envelope("lecture_draft_updated", { version_id: "ver-2" })));
    expect(result.current.turns[0].hadDraftEdit).toBe(true);
  });

  it("surfaces voice_unavailable as a notice without erroring", () => {
    const { result } = renderHook(() => useLectureVoiceSession("lec-1", "en"));
    act(() => result.current.startSession());
    const ws = FakeWebSocket.instances[0];
    act(() => ws.emitMessage(envelope("connected", {})));

    act(() =>
      ws.emitMessage(
        envelope("voice_unavailable", {
          notice: "voice not yet available in sd; reading aloud disabled.",
        })
      )
    );

    expect(result.current.unavailableNotice).toContain("not yet available");
    expect(result.current.status).toBe("ready");
  });

  it("surfaces error messages as a terminal error state", () => {
    const { result } = renderHook(() => useLectureVoiceSession("lec-1", "en"));
    act(() => result.current.startSession());
    const ws = FakeWebSocket.instances[0];
    act(() => ws.emitMessage(envelope("connected", {})));

    act(() => ws.emitMessage(envelope("error", { reason: "turn_processing_failed" })));

    expect(result.current.status).toBe("error");
    expect(result.current.errorReason).toBe("turn_processing_failed");
  });

  it("endSession sends voice_session_end and closes the socket", () => {
    const { result } = renderHook(() => useLectureVoiceSession("lec-1", "en"));
    act(() => result.current.startSession());
    const ws = FakeWebSocket.instances[0];
    act(() => ws.emitMessage(envelope("connected", {})));

    act(() => result.current.endSession());

    const endMessages = ws.sent.map((s) => JSON.parse(s)).filter((m) => m.type === "voice_session_end");
    expect(endMessages).toHaveLength(1);
    expect(ws.readyState).toBe(3);
  });
});
