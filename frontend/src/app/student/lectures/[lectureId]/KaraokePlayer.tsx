"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import type { LectureAudioAlignmentSpan, LectureAudioCacheRead } from "@/lib/api";

const SPEEDS = [0.5, 0.75, 1, 1.25, 1.5, 2] as const;

type Props = {
  audio: LectureAudioCacheRead;
  downloadHref: string;
  onActiveSpanChange: (span: LectureAudioAlignmentSpan | null) => void;
  onStopRequest?: () => void;
  active: boolean;
};

export function KaraokePlayer({
  audio,
  downloadHref,
  onActiveSpanChange,
  active,
}: Props) {
  const t = useTranslations("student.lecture_viewer");
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [playing, setPlaying] = useState(false);
  const [speedIdx, setSpeedIdx] = useState(2); // 1x
  const [currentMs, setCurrentMs] = useState(0);

  const alignment = audio.alignment ?? [];

  const activeSpan = useMemo(() => {
    return (
      alignment.find((span) => currentMs >= span.start_ms && currentMs < span.end_ms) ??
      null
    );
  }, [alignment, currentMs]);

  useEffect(() => {
    onActiveSpanChange(activeSpan);
  }, [activeSpan, onActiveSpanChange]);

  useEffect(() => {
    const el = audioRef.current;
    if (!el) return;
    if (!active) {
      el.pause();
      setPlaying(false);
      return;
    }
    const playResult = el.play();
    // jsdom's HTMLMediaElement.play() may return undefined (not a Promise).
    if (playResult && typeof (playResult as Promise<void>).then === "function") {
      void playResult.then(() => setPlaying(true)).catch(() => setPlaying(false));
    } else {
      setPlaying(true);
    }
  }, [active, audio.audio_url]);

  useEffect(() => {
    const el = audioRef.current;
    if (!el) return;
    el.playbackRate = SPEEDS[speedIdx] ?? 1;
  }, [speedIdx]);

  const onTimeUpdate = useCallback(() => {
    const el = audioRef.current;
    if (!el) return;
    setCurrentMs(Math.floor(el.currentTime * 1000));
  }, []);

  const togglePlay = () => {
    const el = audioRef.current;
    if (!el) return;
    if (el.paused) {
      const playResult = el.play();
      if (playResult && typeof (playResult as Promise<void>).then === "function") {
        void playResult.then(() => setPlaying(true)).catch(() => setPlaying(false));
      } else {
        setPlaying(true);
      }
    } else {
      el.pause();
      setPlaying(false);
    }
  };

  const seekBy = (deltaSec: number) => {
    const el = audioRef.current;
    if (!el) return;
    el.currentTime = Math.max(0, Math.min(el.duration || 0, el.currentTime + deltaSec));
    setCurrentMs(Math.floor(el.currentTime * 1000));
  };

  const cycleSpeed = () => {
    setSpeedIdx((i) => (i + 1) % SPEEDS.length);
  };

  if (!audio.audio_url) {
    return (
      <p className="text-sm text-amber-700" data-testid="karaoke-waiting">
        {t("audio_preparing")}
      </p>
    );
  }

  return (
    <div
      className="sticky bottom-0 z-20 border-t border-gray-200 bg-white/95 p-3 shadow-sm backdrop-blur"
      data-testid="karaoke-player"
      dir="auto"
    >
      <audio
        ref={audioRef}
        src={audio.audio_url}
        preload="auto"
        onTimeUpdate={onTimeUpdate}
        onEnded={() => setPlaying(false)}
        data-testid="karaoke-audio"
      />
      <div className="mx-auto flex max-w-3xl flex-wrap items-center gap-2">
        <button
          type="button"
          className="rounded-md border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-800 hover:bg-gray-50"
          onClick={togglePlay}
          data-testid="karaoke-play-pause"
          aria-label={playing ? t("pause") : t("play")}
        >
          {playing ? t("pause") : t("play")}
        </button>
        <button
          type="button"
          className="rounded-md border border-gray-300 px-2 py-1.5 text-sm text-gray-800 hover:bg-gray-50"
          onClick={() => seekBy(-10)}
          data-testid="karaoke-seek-back"
          aria-label={t("seek_back")}
        >
          −10s
        </button>
        <button
          type="button"
          className="rounded-md border border-gray-300 px-2 py-1.5 text-sm text-gray-800 hover:bg-gray-50"
          onClick={() => seekBy(10)}
          data-testid="karaoke-seek-forward"
          aria-label={t("seek_forward")}
        >
          +10s
        </button>
        <button
          type="button"
          className="rounded-md border border-gray-300 px-2 py-1.5 text-sm text-gray-800 hover:bg-gray-50"
          onClick={cycleSpeed}
          data-testid="karaoke-speed"
          aria-label={t("speed")}
        >
          {SPEEDS[speedIdx]}×
        </button>
        <a
          href={downloadHref}
          className="rounded-md border border-gray-300 px-3 py-1.5 text-sm font-medium text-blue-700 hover:bg-blue-50"
          data-testid="karaoke-download"
          download
        >
          {t("download_audio")}
        </a>
        <span className="ms-auto text-xs text-gray-500" data-testid="karaoke-time">
          {Math.floor(currentMs / 1000)}s
          {audio.duration_ms != null ? ` / ${Math.floor(audio.duration_ms / 1000)}s` : ""}
        </span>
      </div>
    </div>
  );
}
