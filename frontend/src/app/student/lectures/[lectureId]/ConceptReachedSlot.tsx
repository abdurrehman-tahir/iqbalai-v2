"use client";

/**
 * Renders the enrichment card only once the student actually *reaches* the
 * concept (its first paragraph scrolls into view) — that is the moment the
 * per-concept cache is consulted / generation is triggered (T-190, flow-6 §3.10).
 */

import { useEffect, useRef, useState } from "react";
import type { LectureConceptRead } from "@/lib/api";
import { ConceptEnrichmentCard } from "./ConceptEnrichmentCard";

type Props = { lectureId: string; concept: LectureConceptRead };

export function ConceptReachedSlot({ lectureId, concept }: Props) {
  const sentinel = useRef<HTMLDivElement | null>(null);
  const [reached, setReached] = useState(false);

  useEffect(() => {
    if (reached) return;
    const el = sentinel.current;
    if (!el || typeof IntersectionObserver === "undefined") {
      setReached(true); // no observer (old browser / test env) → show immediately
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setReached(true);
          observer.disconnect();
        }
      },
      { rootMargin: "0px 0px 120px 0px" },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [reached]);

  return (
    <div
      ref={sentinel}
      data-testid="concept-slot"
      data-concept-id={concept.concept_id}
    >
      {reached ? (
        <ConceptEnrichmentCard lectureId={lectureId} concept={concept} />
      ) : null}
    </div>
  );
}
