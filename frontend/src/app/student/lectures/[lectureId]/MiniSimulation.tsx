"use client";

/**
 * Interactive mini-simulation (T-191, flow-6 §3.10): sliders from the
 * concept's declarative spec, an output computed with the safe expression
 * evaluator, and per-student state saved (debounced) + restored on return.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useFormatter, useTranslations } from "next-intl";
import { conceptEnrichmentApi, type MiniSimSpecRead } from "@/lib/api";
import { useClientAuth } from "@/hooks/use-client-auth";
import { Skeleton } from "@/components/ui/skeleton";
import { evaluateExpression, ExpressionError } from "./mini-sim-expression";

export const SIM_SAVE_DEBOUNCE_MS = 600;

type Props = { lectureId: string; conceptId: string; spec: MiniSimSpecRead };

function defaults(spec: MiniSimSpecRead): Record<string, number> {
  return Object.fromEntries(spec.variables.map((v) => [v.key, v.default]));
}

export function MiniSimulation({ lectureId, conceptId, spec }: Props) {
  const t = useTranslations("student.enrichment");
  const format = useFormatter();
  const { mounted, token } = useClientAuth();
  const [values, setValues] = useState<Record<string, number>>(() =>
    defaults(spec),
  );
  const [restored, setRestored] = useState(false);
  const saveTimer = useRef<number | undefined>(undefined);

  const progress = useQuery({
    queryKey: ["student", "simulation", lectureId, conceptId],
    queryFn: () =>
      conceptEnrichmentApi.getSimulation(token!, lectureId, conceptId),
    enabled: mounted && !!token,
    staleTime: Infinity,
  });

  // Restore saved state once (per-student, server-side).
  useEffect(() => {
    if (restored || !progress.data) return;
    setValues({ ...defaults(spec), ...progress.data.values });
    setRestored(true);
  }, [progress.data, restored, spec]);

  const save = useMutation({
    mutationFn: (next: Record<string, number>) =>
      conceptEnrichmentApi.saveSimulation(token!, lectureId, conceptId, {
        values: next,
      }),
  });

  useEffect(() => () => window.clearTimeout(saveTimer.current), []);

  const onChange = (key: string, raw: string) => {
    const next = { ...values, [key]: Number(raw) };
    setValues(next);
    window.clearTimeout(saveTimer.current);
    saveTimer.current = window.setTimeout(
      () => save.mutate(next),
      SIM_SAVE_DEBOUNCE_MS,
    );
  };

  const output = useMemo(() => {
    try {
      return evaluateExpression(spec.output.expression, values);
    } catch (err) {
      if (err instanceof ExpressionError) return null;
      throw err;
    }
  }, [spec.output.expression, values]);

  if (progress.isLoading) {
    return <Skeleton className="h-32 w-full" data-testid="mini-sim-loading" />;
  }

  return (
    <section
      className="space-y-3 rounded-md border border-sky-200 bg-sky-50 p-3"
      aria-labelledby={`mini-sim-${conceptId}`}
      data-testid="mini-sim"
    >
      <div>
        <h4
          id={`mini-sim-${conceptId}`}
          className="text-sm font-semibold text-gray-900"
        >
          {t("sim_heading", { title: spec.title })}
        </h4>
        <p className="text-sm text-gray-700">{spec.scenario}</p>
      </div>
      {progress.data?.was_reset ? (
        <p
          className="text-sm text-amber-800"
          role="status"
          data-testid="mini-sim-reset"
        >
          {t("sim_reset_notice")}
        </p>
      ) : null}
      {progress.isError ? (
        <p className="text-sm text-gray-600" role="status">
          {t("sim_progress_unavailable")}
        </p>
      ) : null}
      {spec.variables.map((v) => {
        const id = `sim-${conceptId}-${v.key}`;
        return (
          <div key={v.key} className="space-y-1">
            <label
              htmlFor={id}
              className="flex justify-between gap-2 text-sm text-gray-800"
            >
              <span>{v.label}</span>
              <span dir="ltr" data-testid={`mini-sim-value-${v.key}`}>
                {format.number(values[v.key] ?? v.default)} {v.unit}
              </span>
            </label>
            <input
              id={id}
              type="range"
              min={v.min}
              max={v.max}
              step={v.step}
              value={values[v.key] ?? v.default}
              onChange={(e) => onChange(v.key, e.target.value)}
              className="h-11 w-full accent-sky-700"
              data-testid={`mini-sim-slider-${v.key}`}
            />
          </div>
        );
      })}
      <p
        className="text-base font-medium text-gray-900"
        aria-live="polite"
        data-testid="mini-sim-output"
      >
        {output === null
          ? t("sim_output_undefined", { label: spec.output.label })
          : t("sim_output", {
              label: spec.output.label,
              value: format.number(output, { maximumFractionDigits: 2 }),
              unit: spec.output.unit,
            })}
      </p>
      {save.isError ? (
        <p className="text-sm text-red-600" role="alert">
          {t("sim_save_error")}
        </p>
      ) : null}
    </section>
  );
}
