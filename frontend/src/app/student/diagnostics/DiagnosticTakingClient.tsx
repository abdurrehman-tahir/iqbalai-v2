"use client";

import { useMutation } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useEffect, useMemo, useState } from "react";
import { diagnosticsApi } from "@/lib/api";
import { useClientAuth } from "@/hooks/use-client-auth";
import { Button } from "@/components/ui/button";
import type { DiagnosticRead, DiagnosticResultRead, DiagnosticStartRequest } from "@/lib/api/types";

type Props = {
  /** School: subject_id; Independent: framework_id */
  startRequest: DiagnosticStartRequest;
};

export function DiagnosticTakingClient({ startRequest }: Props) {
  const t = useTranslations("diagnostics");
  const { mounted, token } = useClientAuth();
  const [diagnostic, setDiagnostic] = useState<DiagnosticRead | null>(null);
  const [result, setResult] = useState<DiagnosticResultRead | null>(null);
  const [index, setIndex] = useState(0);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);

  const startMutation = useMutation({
    mutationFn: () => diagnosticsApi.start(token ?? "", startRequest),
    onSuccess: (data) => {
      setDiagnostic(data);
      setResult(null);
      setError(null);
      const answered = Object.keys(data.answers ?? {}).length;
      setIndex(Math.min(answered, Math.max(0, data.questions.length - 1)));
      const q = data.questions[Math.min(answered, Math.max(0, data.questions.length - 1))];
      const existing = q ? data.answers?.[q.id] : undefined;
      setDraft(typeof existing === "string" ? existing : "");
    },
    onError: (err) => {
      setError(err instanceof Error ? err.message : t("error_generic"));
    },
  });

  const saveMutation = useMutation({
    mutationFn: (answers: Record<string, string>) =>
      diagnosticsApi.saveAnswers(token ?? "", diagnostic!.id, { answers }),
    onSuccess: (data) => {
      setDiagnostic(data);
      setError(null);
    },
    onError: (err) => {
      setError(err instanceof Error ? err.message : t("error_generic"));
    },
  });

  const completeMutation = useMutation({
    mutationFn: () => diagnosticsApi.complete(token ?? "", diagnostic!.id),
    onSuccess: (data) => {
      setResult(data);
      setDiagnostic(data.diagnostic);
      setError(null);
    },
    onError: (err) => {
      setError(err instanceof Error ? err.message : t("error_generic"));
    },
  });

  const timeoutMutation = useMutation({
    mutationFn: () => diagnosticsApi.finalizeTimeout(token ?? "", diagnostic!.id),
    onSuccess: (data) => {
      setResult(data);
      setDiagnostic(data.diagnostic);
      setError(null);
    },
    onError: (err) => {
      setError(err instanceof Error ? err.message : t("error_generic"));
    },
  });

  useEffect(() => {
    if (mounted && token && !diagnostic && !startMutation.isPending && !startMutation.isError) {
      startMutation.mutate();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- start once when auth ready
  }, [mounted, token]);

  useEffect(() => {
    if (!diagnostic?.expires_at || result) return;
    const expiresMs = Date.parse(diagnostic.expires_at);
    if (Number.isNaN(expiresMs)) return;
    const delay = expiresMs - Date.now();
    if (delay <= 0) {
      timeoutMutation.mutate();
      return;
    }
    const handle = window.setTimeout(() => {
      timeoutMutation.mutate();
    }, delay);
    return () => window.clearTimeout(handle);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [diagnostic?.id, diagnostic?.expires_at, result]);

  const questions = diagnostic?.questions ?? [];
  const current = questions[index];
  const progress = useMemo(() => {
    if (!questions.length) return 0;
    return Math.round(((index + 1) / questions.length) * 100);
  }, [index, questions.length]);

  async function persistCurrentAnswer() {
    if (!diagnostic || !current) return;
    const nextAnswers = { ...diagnostic.answers, [current.id]: draft };
    await saveMutation.mutateAsync(
      Object.fromEntries(
        Object.entries(nextAnswers).map(([k, v]) => [k, typeof v === "string" ? v : String(v ?? "")]),
      ),
    );
  }

  if (!mounted || startMutation.isPending || (!diagnostic && !startMutation.isError)) {
    return (
      <div className="mx-auto max-w-2xl" role="status" aria-label={t("loading")}>
        <div className="h-8 w-48 animate-pulse rounded bg-gray-100" />
        <div className="mt-4 h-40 animate-pulse rounded-lg bg-gray-100" />
      </div>
    );
  }

  if (startMutation.isError && !diagnostic) {
    return (
      <div className="mx-auto max-w-2xl space-y-4" role="alert">
        <p className="text-sm text-red-600">{error ?? t("error_generic")}</p>
        <Button variant="primary" onClick={() => startMutation.mutate()}>
          {t("retry")}
        </Button>
      </div>
    );
  }

  if (result) {
    return (
      <div className="mx-auto max-w-2xl space-y-6" data-testid="diagnostic-results">
        <div>
          <h2 className="text-2xl font-semibold text-gray-900">{t("results_title")}</h2>
          <p className="mt-2 text-sm text-gray-600">{result.coaching_summary}</p>
          {result.timed_out && (
            <p className="mt-2 text-sm text-amber-800">{t("timeout_notice")}</p>
          )}
        </div>
        <section className="rounded-lg border border-gray-200 bg-white p-4 space-y-3">
          <h3 className="text-lg font-medium text-gray-900">{t("focus_areas_title")}</h3>
          {!result.focus_areas.length ? (
            <p className="text-sm text-gray-500">{t("focus_areas_empty")}</p>
          ) : (
            <ul className="space-y-3">
              {result.focus_areas.map((area) => (
                <li key={area.topic} className="rounded-md border border-gray-100 p-3">
                  <p className="text-sm font-medium text-gray-900">{area.topic}</p>
                  <p className="mt-1 text-sm text-gray-600">{area.suggestion}</p>
                </li>
              ))}
            </ul>
          )}
        </section>
        <p className="text-xs text-gray-500">{t("no_grades_disclaimer")}</p>
      </div>
    );
  }

  if (!current) {
    return (
      <div className="mx-auto max-w-2xl space-y-4">
        <p className="text-sm text-gray-600">{t("empty_questions")}</p>
        <Button
          variant="primary"
          loading={completeMutation.isPending}
          onClick={() => completeMutation.mutate()}
        >
          {t("finish")}
        </Button>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6" data-testid="diagnostic-taking">
      <div>
        <h2 className="text-2xl font-semibold text-gray-900">{t("title")}</h2>
        <p className="mt-2 text-sm text-gray-600">{t("subtitle")}</p>
        <p className="mt-3 text-sm text-gray-700" aria-live="polite">
          {t("progress", { current: index + 1, total: questions.length, percent: progress })}
        </p>
        <div
          className="mt-2 h-2 w-full overflow-hidden rounded-full bg-gray-100"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={progress}
          aria-label={t("progress_bar_label")}
        >
          <div
            className={`h-full bg-brand-600 transition-all ${
              progress >= 100
                ? "w-full"
                : progress >= 75
                  ? "w-3/4"
                  : progress >= 50
                    ? "w-1/2"
                    : progress >= 25
                      ? "w-1/4"
                      : progress > 0
                        ? "w-1/12"
                        : "w-0"
            }`}
          />
        </div>
      </div>

      <section className="rounded-lg border border-gray-200 bg-white p-4 space-y-4">
        <p className="text-base text-gray-900">{current.prompt}</p>
        {current.choices?.length ? (
          <fieldset className="space-y-2">
            <legend className="sr-only">{t("choices_legend")}</legend>
            {current.choices.map((choice) => (
              <label
                key={choice}
                className="flex min-h-11 cursor-pointer items-center gap-3 rounded-md border border-gray-100 px-3 py-2"
              >
                <input
                  type="radio"
                  name={`q-${current.id}`}
                  value={choice}
                  checked={draft === choice}
                  onChange={() => setDraft(choice)}
                  className="size-4"
                />
                <span className="text-sm text-gray-800">{choice}</span>
              </label>
            ))}
          </fieldset>
        ) : (
          <label className="block space-y-2">
            <span className="text-sm text-gray-700">{t("open_answer_label")}</span>
            <textarea
              className="min-h-24 w-full rounded-md border border-gray-200 p-3 text-sm"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
            />
          </label>
        )}
      </section>

      {error && (
        <p className="text-sm text-red-600" role="alert">
          {error}
        </p>
      )}

      <div className="flex flex-wrap gap-3">
        <Button
          variant="ghost"
          size="sm"
          disabled={index === 0 || saveMutation.isPending}
          onClick={async () => {
            await persistCurrentAnswer();
            setIndex((i) => Math.max(0, i - 1));
            const prev = questions[Math.max(0, index - 1)];
            const existing = prev ? diagnostic?.answers?.[prev.id] : undefined;
            setDraft(typeof existing === "string" ? existing : "");
          }}
        >
          {t("previous")}
        </Button>
        <Button
          variant="ghost"
          size="sm"
          loading={saveMutation.isPending}
          onClick={() => void persistCurrentAnswer()}
        >
          {t("save_pause")}
        </Button>
        {index < questions.length - 1 ? (
          <Button
            variant="primary"
            size="sm"
            loading={saveMutation.isPending}
            onClick={async () => {
              await persistCurrentAnswer();
              const nextIndex = index + 1;
              setIndex(nextIndex);
              const next = questions[nextIndex];
              const existing = next ? diagnostic?.answers?.[next.id] : undefined;
              setDraft(typeof existing === "string" ? existing : "");
            }}
          >
            {t("next")}
          </Button>
        ) : (
          <Button
            variant="primary"
            size="sm"
            loading={completeMutation.isPending || saveMutation.isPending}
            onClick={async () => {
              await persistCurrentAnswer();
              completeMutation.mutate();
            }}
          >
            {t("finish")}
          </Button>
        )}
      </div>
    </div>
  );
}
