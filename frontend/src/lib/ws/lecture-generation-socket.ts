"use client";

import { useEffect, useRef, useState } from "react";
import { API_BASE } from "@/lib/api";

/**
 * Locked client behavior (ARCH §9.14 / §16.9): heartbeat every 25s, force
 * reconnect if the server has been silent for 60s, reconnect backoff
 * 1s/2s/4s/8s capped at 30s with jitter.
 */
const CLIENT_HEARTBEAT_MS = 25_000;
const STALE_CONNECTION_MS = 60_000;
const RECONNECT_DELAYS_MS = [1_000, 2_000, 4_000, 8_000];
const RECONNECT_MAX_DELAY_MS = 30_000;

export type LectureGenerationStatus =
  | "connecting"
  | "streaming"
  | "reconnecting"
  | "complete"
  | "error";

export interface LectureGenerationState {
  status: LectureGenerationStatus;
  text: string;
  versionId: string | null;
  errorReason: string | null;
}

interface WsEnvelope {
  type: string;
  id: string;
  data: Record<string, unknown>;
  meta: { timestamp: string; request_id: string | null };
}

/** `http(s)://host/api/v1` → `ws(s)://host/ws/v1` — no separate WS env var needed. */
export function deriveWsBaseUrl(apiBase: string): string {
  const withScheme = apiBase.replace(/^http/i, (m) => (m === "https" ? "wss" : "ws"));
  return withScheme.replace(/\/api\/v1\/?$/, "/ws/v1");
}

function reconnectDelayMs(attempt: number): number {
  const base = RECONNECT_DELAYS_MS[attempt] ?? RECONNECT_MAX_DELAY_MS;
  return base + Math.floor(Math.random() * 300);
}

export function useLectureGenerationStream(
  lectureId: string | undefined,
  enabled: boolean
): LectureGenerationState {
  const [state, setState] = useState<LectureGenerationState>({
    status: "connecting",
    text: "",
    versionId: null,
    errorReason: null,
  });

  const socketRef = useRef<WebSocket | null>(null);
  const lastSeqRef = useRef(0);
  const attemptRef = useRef(0);
  const doneRef = useRef(false);
  const heartbeatTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const staleTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!enabled || !lectureId) return undefined;
    doneRef.current = false;

    const clearTimers = () => {
      if (heartbeatTimerRef.current) clearInterval(heartbeatTimerRef.current);
      if (staleTimerRef.current) clearTimeout(staleTimerRef.current);
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
    };

    const armStaleWatchdog = () => {
      if (staleTimerRef.current) clearTimeout(staleTimerRef.current);
      staleTimerRef.current = setTimeout(() => {
        socketRef.current?.close();
      }, STALE_CONNECTION_MS);
    };

    const scheduleReconnect = () => {
      if (doneRef.current) return;
      setState((prev) => ({ ...prev, status: "reconnecting" }));
      const delay = reconnectDelayMs(attemptRef.current);
      attemptRef.current += 1;
      reconnectTimerRef.current = setTimeout(connect, delay);
    };

    function connect(): void {
      if (doneRef.current) return;
      const base = deriveWsBaseUrl(API_BASE);
      const url = `${base}/lectures/${lectureId}/generation?resume_from=${lastSeqRef.current}`;
      const ws = new WebSocket(url);
      socketRef.current = ws;

      ws.onopen = () => {
        armStaleWatchdog();
      };

      ws.onmessage = (event: MessageEvent<string>) => {
        armStaleWatchdog();
        let envelope: WsEnvelope;
        try {
          envelope = JSON.parse(event.data);
        } catch {
          return;
        }

        switch (envelope.type) {
          case "connected":
            attemptRef.current = 0;
            setState((prev) => ({ ...prev, status: "streaming" }));
            if (heartbeatTimerRef.current) clearInterval(heartbeatTimerRef.current);
            heartbeatTimerRef.current = setInterval(() => {
              ws.send(JSON.stringify({ type: "heartbeat" }));
            }, CLIENT_HEARTBEAT_MS);
            break;
          case "lecture_generation_token": {
            const seq = Number(envelope.data.seq ?? 0);
            const token = String(envelope.data.token ?? "");
            if (seq > lastSeqRef.current) {
              lastSeqRef.current = seq;
              setState((prev) => ({ ...prev, text: prev.text + token }));
            }
            break;
          }
          case "lecture_generation_complete":
            doneRef.current = true;
            setState((prev) => ({
              ...prev,
              status: "complete",
              versionId: String(envelope.data.version_id ?? ""),
            }));
            clearTimers();
            ws.close(1000);
            break;
          case "error":
            doneRef.current = true;
            setState((prev) => ({
              ...prev,
              status: "error",
              errorReason: String(envelope.data.reason ?? "generation_failed"),
            }));
            clearTimers();
            ws.close();
            break;
          default:
            break;
        }
      };

      ws.onclose = () => {
        if (heartbeatTimerRef.current) clearInterval(heartbeatTimerRef.current);
        if (staleTimerRef.current) clearTimeout(staleTimerRef.current);
        if (!doneRef.current) scheduleReconnect();
      };
    }

    connect();

    return () => {
      doneRef.current = true;
      clearTimers();
      socketRef.current?.close();
      socketRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lectureId, enabled]);

  return state;
}
