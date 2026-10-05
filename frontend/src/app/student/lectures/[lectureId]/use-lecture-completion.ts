"use client";

/**
 * Lecture completion signal (T-192, flow-6 §3.11): the lecture counts as
 * completed when its end is on screen OR at least 80% of it has been scrolled
 * into view. To avoid prompting on a short lecture the instant it opens, the
 * signal also requires real engagement: a scroll by the student, or
 * MIN_DWELL_MS on the page.
 */

import { useEffect, useState, type RefObject } from "react";

export const COMPLETION_THRESHOLD = 0.8;
export const MIN_DWELL_MS = 30_000;

/** Pure check: share of the lecture element that has entered the viewport. */
export function hasReachedCompletion(
  rect: { top: number; height: number },
  viewportHeight: number,
): boolean {
  if (rect.height <= 0) return false;
  const seen = Math.min(rect.height, Math.max(0, viewportHeight - rect.top));
  return seen / rect.height >= COMPLETION_THRESHOLD;
}

export function useLectureCompletion(
  target: RefObject<HTMLElement | null>,
  enabled: boolean,
): boolean {
  const [completed, setCompleted] = useState(false);

  useEffect(() => {
    if (!enabled || completed) return;
    let engaged = false;
    let reached = false;

    const evaluate = () => {
      const el = target.current;
      if (!el) return;
      reached =
        reached ||
        hasReachedCompletion(el.getBoundingClientRect(), window.innerHeight);
      if (reached && engaged) setCompleted(true);
    };
    const onScroll = () => {
      engaged = true;
      evaluate();
    };
    const dwell = window.setTimeout(() => {
      engaged = true;
      evaluate();
    }, MIN_DWELL_MS);

    window.addEventListener("scroll", onScroll, {
      passive: true,
      capture: true,
    });
    window.addEventListener("resize", evaluate);
    evaluate();
    return () => {
      window.clearTimeout(dwell);
      window.removeEventListener("scroll", onScroll, { capture: true });
      window.removeEventListener("resize", evaluate);
    };
  }, [completed, enabled, target]);

  return completed;
}
