"use client";

/**
 * Voice transcription via MediaRecorder + faster-whisper HTTP STT (T-155).
 *
 * Live feel: every timeslice re-transcribes the growing recording so partial
 * text appears in the input. Stops on tap-again / ESC / 30s silence / 60s max.
 *
 * Uses POST /students/me/voice/transcribe (teacher voice-transcribe pattern) —
 * no invented WebSocket STT transport.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import type { VoiceLanguage } from "../types";

const SILENCE_MS = 30_000;
const MAX_RECORDING_MS = 60_000;
const TIMESLICE_MS = 2_500;
const SILENCE_RMS_THRESHOLD = 0.01;

export type VoicePermission = "granted" | "denied" | "prompt" | "unavailable";

export type UseVoiceTranscriptionOptions = {
  language?: VoiceLanguage;
  enabled?: boolean;
  /** Called with the best-so-far transcript for this recording session. */
  onPartialTranscript?: (text: string) => void;
  /** Called once after stop with the final session transcript. */
  onFinalTranscript?: (text: string) => void;
  onRecordingStart?: () => void;
  onRecordingStop?: () => void;
  onError?: (code: "mic_permission_denied" | "voice_error" | "voice_unavailable") => void;
  transcribeAudio?: (
    audio: Blob,
    language?: VoiceLanguage
  ) => Promise<{ transcript: string }>;
};

export function useVoiceTranscription(options: UseVoiceTranscriptionOptions = {}) {
  const {
    language,
    enabled = true,
    onPartialTranscript,
    onFinalTranscript,
    onRecordingStart,
    onRecordingStop,
    onError,
    transcribeAudio,
  } = options;

  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [permission, setPermission] = useState<VoicePermission>("prompt");

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const lastSessionTextRef = useRef("");
  const transcribeChainRef = useRef<Promise<void>>(Promise.resolve());
  const maxTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const rafRef = useRef<number | null>(null);
  const lastVoiceAtRef = useRef<number>(0);
  const stoppedRef = useRef(false);

  const clearTimers = useCallback(() => {
    if (maxTimerRef.current) clearTimeout(maxTimerRef.current);
    maxTimerRef.current = null;
    if (rafRef.current != null) cancelAnimationFrame(rafRef.current);
    rafRef.current = null;
  }, []);

  const stopStream = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    void audioCtxRef.current?.close().catch(() => undefined);
    audioCtxRef.current = null;
    analyserRef.current = null;
  }, []);

  const transcribeBlob = useCallback(
    async (blob: Blob): Promise<string> => {
      if (!transcribeAudio || blob.size === 0) return "";
      const result = await transcribeAudio(blob, language);
      return (result.transcript ?? "").trim();
    },
    [language, transcribeAudio]
  );

  const stop = useCallback(() => {
    if (stoppedRef.current) return;
    stoppedRef.current = true;
    clearTimers();
    const recorder = mediaRecorderRef.current;
    if (recorder && recorder.state !== "inactive") {
      recorder.stop();
    } else {
      stopStream();
      setIsRecording(false);
      onRecordingStop?.();
    }
  }, [clearTimers, onRecordingStop, stopStream]);

  const monitorSilence = useCallback(() => {
    const analyser = analyserRef.current;
    if (!analyser) return;
    const data = new Uint8Array(analyser.fftSize);
    const tick = () => {
      if (stoppedRef.current) return;
      analyser.getByteTimeDomainData(data);
      let sum = 0;
      for (let i = 0; i < data.length; i++) {
        const v = (data[i]! - 128) / 128;
        sum += v * v;
      }
      const rms = Math.sqrt(sum / data.length);
      const now = Date.now();
      if (rms > SILENCE_RMS_THRESHOLD) {
        lastVoiceAtRef.current = now;
      } else if (now - lastVoiceAtRef.current >= SILENCE_MS) {
        stop();
        return;
      }
      rafRef.current = requestAnimationFrame(tick);
    };
    lastVoiceAtRef.current = Date.now();
    rafRef.current = requestAnimationFrame(tick);
  }, [stop]);

  const start = useCallback(async () => {
    if (!enabled || isRecording) return;
    if (!transcribeAudio) {
      onError?.("voice_unavailable");
      return;
    }
    if (typeof MediaRecorder === "undefined" || !navigator.mediaDevices?.getUserMedia) {
      setPermission("unavailable");
      onError?.("mic_permission_denied");
      return;
    }

    stoppedRef.current = false;
    chunksRef.current = [];
    lastSessionTextRef.current = "";
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      setPermission("granted");
      streamRef.current = stream;

      try {
        const ctx = new AudioContext();
        audioCtxRef.current = ctx;
        const source = ctx.createMediaStreamSource(stream);
        const analyser = ctx.createAnalyser();
        analyser.fftSize = 2048;
        source.connect(analyser);
        analyserRef.current = analyser;
      } catch {
        // Silence detection optional.
      }

      const recorder = new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (event: BlobEvent) => {
        if (event.data.size <= 0) return;
        chunksRef.current.push(event.data);
        const growing = new Blob(chunksRef.current, {
          type: recorder.mimeType || "audio/webm",
        });
        transcribeChainRef.current = transcribeChainRef.current.then(async () => {
          if (stoppedRef.current) return;
          try {
            const text = await transcribeBlob(growing);
            if (text) {
              lastSessionTextRef.current = text;
              onPartialTranscript?.(text);
            }
          } catch {
            // Partial failures are non-fatal.
          }
        });
      };

      recorder.onstop = () => {
        clearTimers();
        stopStream();
        setIsRecording(false);
        onRecordingStop?.();
        const blob = new Blob(chunksRef.current, {
          type: recorder.mimeType || "audio/webm",
        });
        chunksRef.current = [];
        setIsTranscribing(true);
        void transcribeChainRef.current
          .then(() => transcribeBlob(blob))
          .then((text) => {
            const finalText = text || lastSessionTextRef.current;
            if (finalText) onFinalTranscript?.(finalText);
          })
          .catch(() => {
            if (lastSessionTextRef.current) {
              onFinalTranscript?.(lastSessionTextRef.current);
            } else {
              onError?.("voice_error");
            }
          })
          .finally(() => setIsTranscribing(false));
      };

      recorder.start(TIMESLICE_MS);
      setIsRecording(true);
      onRecordingStart?.();
      monitorSilence();
      maxTimerRef.current = setTimeout(() => stop(), MAX_RECORDING_MS);
    } catch {
      setPermission("denied");
      stopStream();
      onError?.("mic_permission_denied");
    }
  }, [
    clearTimers,
    enabled,
    isRecording,
    monitorSilence,
    onError,
    onFinalTranscript,
    onPartialTranscript,
    onRecordingStart,
    onRecordingStop,
    stop,
    stopStream,
    transcribeAudio,
    transcribeBlob,
  ]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isRecording) {
        e.preventDefault();
        stop();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [isRecording, stop]);

  useEffect(() => {
    return () => {
      stoppedRef.current = true;
      clearTimers();
      mediaRecorderRef.current?.stop();
      stopStream();
    };
  }, [clearTimers, stopStream]);

  const toggle = useCallback(async () => {
    if (isRecording) stop();
    else await start();
  }, [isRecording, start, stop]);

  return {
    isRecording,
    isTranscribing,
    permission,
    start,
    stop,
    toggle,
  };
}
