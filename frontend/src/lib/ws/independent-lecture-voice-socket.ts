"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { API_BASE } from "@/lib/api";
import { deriveWsBaseUrl } from "./lecture-generation-socket";

/**
 * Independent teacher voice conversation (T-125) — mirrors
 * `lecture-voice-socket.ts` exactly, pointed at the independent-schema WS
 * endpoint (`/ws/v1/independent/lectures/{lectureId}/voice`, a distinct path
 * from the school variant so the two never collide at the router level).
 */

const CLIENT_HEARTBEAT_MS = 25_000;
const RECORDER_TIMESLICE_MS = 500;

export type VoiceSessionStatus =
  | "idle"
  | "connecting"
  | "ready"
  | "recording"
  | "processing"
  | "ended"
  | "error";

export interface VoiceTurnRecord {
  transcript: string;
  confirmation: string;
  hadDraftEdit: boolean;
}

export interface VoiceSessionState {
  status: VoiceSessionStatus;
  turns: VoiceTurnRecord[];
  errorReason: string | null;
  unavailableNotice: string | null;
}

export interface VoiceSessionControls {
  startSession: () => void;
  endSession: () => void;
  startRecording: () => Promise<void>;
  stopRecording: () => void;
}

interface WsEnvelope {
  type: string;
  id: string;
  data: Record<string, unknown>;
  meta: { timestamp: string; request_id: string | null };
}

function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => {
      const result = String(reader.result ?? "");
      resolve(result.includes(",") ? result.split(",")[1] : result);
    };
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });
}

function base64ToBlob(base64: string, mimeType: string): Blob {
  const byteChars = atob(base64);
  const byteNumbers = new Array(byteChars.length);
  for (let i = 0; i < byteChars.length; i++) {
    byteNumbers[i] = byteChars.charCodeAt(i);
  }
  return new Blob([new Uint8Array(byteNumbers)], { type: mimeType });
}

export function useIndependentLectureVoiceSession(
  lectureId: string | undefined,
  language: string
): VoiceSessionState & VoiceSessionControls {
  const [state, setState] = useState<VoiceSessionState>({
    status: "idle",
    turns: [],
    errorReason: null,
    unavailableNotice: null,
  });

  const socketRef = useRef<WebSocket | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const heartbeatTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopMicrophone = useCallback(() => {
    mediaRecorderRef.current?.stop();
    mediaRecorderRef.current = null;
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
  }, []);

  const startSession = useCallback(() => {
    if (!lectureId || socketRef.current) return;
    setState({ status: "connecting", turns: [], errorReason: null, unavailableNotice: null });

    const base = deriveWsBaseUrl(API_BASE);
    const ws = new WebSocket(
      `${base}/independent/lectures/${lectureId}/voice?language=${encodeURIComponent(language)}`
    );
    socketRef.current = ws;

    ws.onopen = () => {
      heartbeatTimerRef.current = setInterval(() => {
        ws.send(JSON.stringify({ type: "heartbeat" }));
      }, CLIENT_HEARTBEAT_MS);
    };

    ws.onmessage = (event: MessageEvent<string>) => {
      let envelope: WsEnvelope;
      try {
        envelope = JSON.parse(event.data);
      } catch {
        return;
      }

      switch (envelope.type) {
        case "connected":
          setState((prev) => ({ ...prev, status: "ready" }));
          break;
        case "voice_transcript":
          setState((prev) => ({
            ...prev,
            status: "ready",
            turns: [
              ...prev.turns,
              {
                transcript: String(envelope.data.transcript ?? ""),
                confirmation: String(envelope.data.confirmation ?? ""),
                hadDraftEdit: false,
              },
            ],
          }));
          break;
        case "lecture_draft_updated":
          setState((prev) => {
            if (prev.turns.length === 0) return prev;
            const turns = [...prev.turns];
            turns[turns.length - 1] = { ...turns[turns.length - 1], hadDraftEdit: true };
            return { ...prev, turns };
          });
          break;
        case "voice_audio_response": {
          const audioBase64 = String(envelope.data.audio_base64 ?? "");
          const mimeType = String(envelope.data.mime_type ?? "audio/wav");
          if (audioBase64) {
            const blob = base64ToBlob(audioBase64, mimeType);
            const url = URL.createObjectURL(blob);
            const audio = new Audio(url);
            audio.onended = () => URL.revokeObjectURL(url);
            void audio.play();
          }
          break;
        }
        case "voice_unavailable":
          setState((prev) => ({
            ...prev,
            unavailableNotice: String(envelope.data.notice ?? ""),
          }));
          break;
        case "error":
          setState((prev) => ({
            ...prev,
            status: "error",
            errorReason: String(envelope.data.reason ?? "unknown_error"),
          }));
          break;
        default:
          break;
      }
    };

    ws.onclose = () => {
      if (heartbeatTimerRef.current) clearInterval(heartbeatTimerRef.current);
      stopMicrophone();
      socketRef.current = null;
      setState((prev) => (prev.status === "error" ? prev : { ...prev, status: "ended" }));
    };
  }, [lectureId, language, stopMicrophone]);

  const endSession = useCallback(() => {
    stopMicrophone();
    const ws = socketRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "voice_session_end", data: {} }));
    }
    ws?.close();
  }, [stopMicrophone]);

  const startRecording = useCallback(async () => {
    const ws = socketRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return;

    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    streamRef.current = stream;
    const recorder = new MediaRecorder(stream);
    mediaRecorderRef.current = recorder;

    recorder.ondataavailable = (event: BlobEvent) => {
      if (event.data.size === 0) return;
      void blobToBase64(event.data).then((audio_base64) => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: "voice_audio_chunk", data: { audio_base64 } }));
        }
      });
    };

    recorder.start(RECORDER_TIMESLICE_MS);
    setState((prev) => ({ ...prev, status: "recording" }));
  }, []);

  const stopRecording = useCallback(() => {
    stopMicrophone();
    const ws = socketRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "voice_turn_end", data: {} }));
    }
    setState((prev) => ({ ...prev, status: "processing" }));
  }, [stopMicrophone]);

  useEffect(() => {
    return () => {
      if (heartbeatTimerRef.current) clearInterval(heartbeatTimerRef.current);
      stopMicrophone();
      socketRef.current?.close();
      socketRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { ...state, startSession, endSession, startRecording, stopRecording };
}
