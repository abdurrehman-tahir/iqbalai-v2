/**
 * T-117 — useLectureGenerationStream: reconnect/backoff, resume-from-seq, and
 * the locked WS message envelope handling (ARCH §5.12/§9.14).
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { deriveWsBaseUrl, useLectureGenerationStream } from "../lecture-generation-socket";

vi.mock("@/lib/api", () => ({
  API_BASE: "http://localhost:8000/api/v1",
}));

class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  url: string;
  sent: string[] = [];
  closed = false;
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;

  constructor(url: string) {
    this.url = url;
    FakeWebSocket.instances.push(this);
  }

  send(data: string): void {
    this.sent.push(data);
  }

  close(): void {
    this.closed = true;
    this.onclose?.();
  }

  emitOpen(): void {
    this.onopen?.();
  }

  emitMessage(payload: unknown): void {
    this.onmessage?.({ data: JSON.stringify(payload) });
  }
}

function envelope(type: string, data: Record<string, unknown>) {
  return { type, id: "m-1", data, meta: { timestamp: "2026-07-31T00:00:00Z", request_id: null } };
}

beforeEach(() => {
  FakeWebSocket.instances = [];
  vi.stubGlobal("WebSocket", FakeWebSocket);
  vi.spyOn(Math, "random").mockReturnValue(0);
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("deriveWsBaseUrl", () => {
  it("swaps http scheme and /api/v1 path for ws + /ws/v1", () => {
    expect(deriveWsBaseUrl("http://localhost:8000/api/v1")).toBe("ws://localhost:8000/ws/v1");
  });

  it("swaps https scheme for wss", () => {
    expect(deriveWsBaseUrl("https://api.iqbalai.example/api/v1")).toBe(
      "wss://api.iqbalai.example/ws/v1"
    );
  });
});

describe("useLectureGenerationStream", () => {
  it("connects to the lecture's generation channel with resume_from=0 initially", () => {
    renderHook(() => useLectureGenerationStream("lec-1", true));

    expect(FakeWebSocket.instances).toHaveLength(1);
    expect(FakeWebSocket.instances[0].url).toBe(
      "ws://localhost:8000/ws/v1/lectures/lec-1/generation?resume_from=0"
    );
  });

  it("does not connect when disabled or lectureId is missing", () => {
    renderHook(() => useLectureGenerationStream(undefined, true));
    renderHook(() => useLectureGenerationStream("lec-1", false));

    expect(FakeWebSocket.instances).toHaveLength(0);
  });

  it("transitions to streaming on `connected` and starts the client heartbeat", () => {
    const { result } = renderHook(() => useLectureGenerationStream("lec-1", true));
    const ws = FakeWebSocket.instances[0];

    act(() => ws.emitMessage(envelope("connected", { heartbeat_interval_seconds: 30 })));

    expect(result.current.status).toBe("streaming");

    act(() => vi.advanceTimersByTime(25_000));
    expect(ws.sent).toEqual([JSON.stringify({ type: "heartbeat" })]);
  });

  it("accumulates tokens in order and ignores stale/duplicate seqs", () => {
    const { result } = renderHook(() => useLectureGenerationStream("lec-1", true));
    const ws = FakeWebSocket.instances[0];
    act(() => ws.emitMessage(envelope("connected", { heartbeat_interval_seconds: 30 })));

    act(() => {
      ws.emitMessage(envelope("lecture_generation_token", { seq: 1, token: "Newton's " }));
      ws.emitMessage(envelope("lecture_generation_token", { seq: 2, token: "first law" }));
      ws.emitMessage(envelope("lecture_generation_token", { seq: 1, token: "IGNORED" }));
    });

    expect(result.current.text).toBe("Newton's first law");
  });

  it("marks complete, closes the socket, and does not reconnect", () => {
    const { result } = renderHook(() => useLectureGenerationStream("lec-1", true));
    const ws = FakeWebSocket.instances[0];
    act(() => ws.emitMessage(envelope("connected", {})));

    act(() => ws.emitMessage(envelope("lecture_generation_complete", { version_id: "ver-1" })));

    expect(result.current.status).toBe("complete");
    expect(result.current.versionId).toBe("ver-1");
    expect(ws.closed).toBe(true);

    act(() => vi.advanceTimersByTime(30_000));
    expect(FakeWebSocket.instances).toHaveLength(1); // no reconnect after completion
  });

  it("surfaces an `error` message as a terminal error state", () => {
    const { result } = renderHook(() => useLectureGenerationStream("lec-1", true));
    const ws = FakeWebSocket.instances[0];
    act(() => ws.emitMessage(envelope("connected", {})));

    act(() => ws.emitMessage(envelope("error", { reason: "timed_out" })));

    expect(result.current.status).toBe("error");
    expect(result.current.errorReason).toBe("timed_out");

    act(() => vi.advanceTimersByTime(30_000));
    expect(FakeWebSocket.instances).toHaveLength(1); // no reconnect after a terminal error
  });

  it("reconnects with resume_from set to the last seen seq on an unexpected close", () => {
    renderHook(() => useLectureGenerationStream("lec-1", true));
    const first = FakeWebSocket.instances[0];
    act(() => {
      first.emitMessage(envelope("connected", {}));
      first.emitMessage(envelope("lecture_generation_token", { seq: 3, token: "states..." }));
      first.onclose?.(); // connection drop, not a clean 1000/complete
    });

    act(() => vi.advanceTimersByTime(1_000)); // first backoff delay (jitter stubbed to 0)

    expect(FakeWebSocket.instances).toHaveLength(2);
    expect(FakeWebSocket.instances[1].url).toBe(
      "ws://localhost:8000/ws/v1/lectures/lec-1/generation?resume_from=3"
    );
  });
});
