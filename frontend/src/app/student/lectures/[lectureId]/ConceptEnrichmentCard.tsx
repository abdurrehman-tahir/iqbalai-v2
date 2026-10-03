"use client";

/**
 * "Why this matters" card shown when the student reaches a concept (T-190/T-191,
 * flow-6 §3.10): real-world uses in Pakistan, career links from the controlled
 * vocabulary, and the interactive mini-simulation. Enrichment is cached per
 * concept server-side; a cache miss returns `pending` and we poll.
 */

import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { Briefcase, Lightbulb } from "lucide-react";
import { conceptEnrichmentApi, type LectureConceptRead } from "@/lib/api";
import { useClientAuth } from "@/hooks/use-client-auth";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { MiniSimulation } from "./MiniSimulation";

export const ENRICHMENT_POLL_MS = 3000;

type Props = { lectureId: string; concept: LectureConceptRead };

export function ConceptEnrichmentCard({ lectureId, concept }: Props) {
  const t = useTranslations("student.enrichment");
  const { mounted, token } = useClientAuth();

  const query = useQuery({
    queryKey: ["student", "concept-enrichment", lectureId, concept.concept_id],
    queryFn: () =>
      conceptEnrichmentApi.getEnrichment(token!, lectureId, concept.concept_id),
    enabled: mounted && !!token,
    refetchInterval: (q) =>
      q.state.data?.status === "pending" ? ENRICHMENT_POLL_MS : false,
  });

  const data = query.data;
  const uses = data?.real_world_uses ?? [];
  const careers = data?.careers ?? [];
  const headingId = `enrichment-${concept.first_paragraph_id}`;

  return (
    <aside
      className="space-y-3 rounded-lg border border-emerald-200 bg-emerald-50/60 p-4"
      aria-labelledby={headingId}
      data-testid="concept-enrichment"
      data-concept-id={concept.concept_id}
      dir="auto"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3
          id={headingId}
          className="flex items-center gap-2 text-base font-semibold text-gray-900"
        >
          <Lightbulb className="size-5 text-emerald-700" aria-hidden="true" />
          {t("heading", { concept: concept.label })}
        </h3>
        {data?.refreshing ? (
          <Badge variant="secondary" data-testid="concept-enrichment-updating">
            {t("updating")}
          </Badge>
        ) : null}
      </div>

      {query.isLoading || data?.status === "pending" ? (
        <div
          className="space-y-2"
          aria-busy="true"
          data-testid="concept-enrichment-pending"
        >
          <p className="text-sm text-gray-600" role="status">
            {t("preparing")}
          </p>
          <Skeleton className="h-16 w-full" />
        </div>
      ) : query.isError || data?.status === "failed" ? (
        <div
          className="space-y-2"
          role="alert"
          data-testid="concept-enrichment-error"
        >
          <p className="text-sm text-gray-700">{t("error")}</p>
          <Button
            variant="outline"
            size="md"
            onClick={() => void query.refetch()}
          >
            {t("retry")}
          </Button>
        </div>
      ) : data &&
        uses.length === 0 &&
        careers.length === 0 &&
        !data.mini_sim ? (
        <p
          className="text-sm text-gray-600"
          data-testid="concept-enrichment-empty"
        >
          {t("empty")}
        </p>
      ) : data ? (
        <div className="space-y-4">
          <section aria-label={t("uses_label")}>
            <h4 className="text-sm font-semibold text-gray-900">
              {t("uses_label")}
            </h4>
            <ul className="mt-1 space-y-2" data-testid="concept-uses">
              {uses.map((use) => (
                <li key={use.title} className="text-sm text-gray-800">
                  <span className="font-medium">{use.title}</span> —{" "}
                  {use.description}
                </li>
              ))}
            </ul>
          </section>

          {careers.length > 0 ? (
            <section aria-label={t("careers_label")}>
              <h4 className="flex items-center gap-1 text-sm font-semibold text-gray-900">
                <Briefcase className="size-4" aria-hidden="true" />
                {t("careers_label")}
              </h4>
              <ul
                className="mt-1 flex flex-wrap gap-2"
                data-testid="concept-careers"
              >
                {careers.map((career) => (
                  <li key={career.id}>
                    <Badge variant="outline" title={career.sector}>
                      {t("career_chip", {
                        name: career.name,
                        sector: career.sector,
                      })}
                    </Badge>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          {data.mini_sim ? (
            <MiniSimulation
              lectureId={lectureId}
              conceptId={concept.concept_id}
              spec={data.mini_sim}
            />
          ) : (
            <p
              className="text-sm text-gray-600"
              data-testid="mini-sim-text-only"
            >
              {t("sim_text_only")}
            </p>
          )}
        </div>
      ) : null}
    </aside>
  );
}
