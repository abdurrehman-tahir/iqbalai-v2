/**
 * T-138 — TeachingInnovationCard (Teaching Innovation Record).
 * Exercises the four UI states + the acted/ignored response flow. Coaching
 * framing only — asserts no score/number text appears anywhere.
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NextIntlClientProvider, useTranslations } from "next-intl";
import en from "../../../../messages/en/common.json";
import { TeachingInnovationCard } from "../TeachingInnovationCard";
import type { CoachingResponseRequest, CoachingSuggestionRead } from "@/lib/api/types";

type ListFn = (token: string) => Promise<CoachingSuggestionRead[]>;
type RespondFn = (
  token: string,
  memoryId: string,
  data: CoachingResponseRequest
) => Promise<CoachingSuggestionRead>;

const SUGGESTION: CoachingSuggestionRead = {
  id: "memory-1",
  weakness_type: "originality",
  suggestion: "Try grounding in local Punjab examples.",
  frequency: 2,
  updated_at: "2026-08-05T00:00:00Z",
};

function TestWrapper({
  listSuggestions,
  respondToSuggestion,
}: {
  listSuggestions: ListFn;
  respondToSuggestion: RespondFn;
}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={client}>
      <NextIntlClientProvider locale="en" messages={en}>
        <Inner listSuggestions={listSuggestions} respondToSuggestion={respondToSuggestion} />
      </NextIntlClientProvider>
    </QueryClientProvider>
  );
}

function Inner({
  listSuggestions,
  respondToSuggestion,
}: {
  listSuggestions: ListFn;
  respondToSuggestion: RespondFn;
}) {
  const t = useTranslations("teacher.lectures.wizard");
  return (
    <TeachingInnovationCard
      token="tok"
      api={{ listSuggestions, respondToSuggestion }}
      t={t}
      queryKeyPrefix="teacher"
    />
  );
}

describe("TeachingInnovationCard", () => {
  it("shows a loading skeleton while suggestions load", () => {
    const listSuggestions = vi.fn(() => new Promise<never>(() => {}));
    const { container } = render(
      <TestWrapper listSuggestions={listSuggestions} respondToSuggestion={vi.fn()} />
    );

    expect(container.querySelectorAll('[class*="animate-pulse"]').length).toBeGreaterThan(0);
  });

  it("shows an error state with retry when suggestions fail to load", async () => {
    const listSuggestions = vi.fn().mockRejectedValue(new Error("network error"));
    const user = userEvent.setup();
    render(<TestWrapper listSuggestions={listSuggestions} respondToSuggestion={vi.fn()} />);

    expect(await screen.findByRole("button", { name: /retry/i })).toBeInTheDocument();
    listSuggestions.mockResolvedValue([]);
    await user.click(screen.getByRole("button", { name: /retry/i }));
    await waitFor(() => expect(listSuggestions).toHaveBeenCalledTimes(2));
  });

  it("renders nothing when there are no pending suggestions", async () => {
    const listSuggestions = vi.fn().mockResolvedValue([]);
    const { container } = render(
      <TestWrapper listSuggestions={listSuggestions} respondToSuggestion={vi.fn()} />
    );

    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });

  it("renders a pending suggestion with no score/number visible anywhere", async () => {
    const listSuggestions = vi.fn().mockResolvedValue([SUGGESTION]);
    render(<TestWrapper listSuggestions={listSuggestions} respondToSuggestion={vi.fn()} />);

    expect(await screen.findByText("Try grounding in local Punjab examples.")).toBeInTheDocument();
    // Coaching framing only (Flow 5 §3.10) — frequency/weakness_type must
    // never leak into the visible text as a score-like number.
    expect(screen.queryByText(/\b2\b/)).not.toBeInTheDocument();
    expect(screen.queryByText(/originality/i)).not.toBeInTheDocument();
  });

  it("marking a suggestion acted calls respondToSuggestion with 'acted'", async () => {
    const listSuggestions = vi.fn().mockResolvedValue([SUGGESTION]);
    const respondToSuggestion = vi.fn().mockResolvedValue({ ...SUGGESTION });
    const user = userEvent.setup();
    render(
      <TestWrapper listSuggestions={listSuggestions} respondToSuggestion={respondToSuggestion} />
    );

    await user.click(await screen.findByRole("button", { name: /I'll try this/i }));

    await waitFor(() =>
      expect(respondToSuggestion).toHaveBeenCalledWith("tok", "memory-1", { response: "acted" })
    );
  });

  it("dismissing a suggestion calls respondToSuggestion with 'ignored'", async () => {
    const listSuggestions = vi.fn().mockResolvedValue([SUGGESTION]);
    const respondToSuggestion = vi.fn().mockResolvedValue({ ...SUGGESTION });
    const user = userEvent.setup();
    render(
      <TestWrapper listSuggestions={listSuggestions} respondToSuggestion={respondToSuggestion} />
    );

    await user.click(await screen.findByRole("button", { name: /Not now/i }));

    await waitFor(() =>
      expect(respondToSuggestion).toHaveBeenCalledWith("tok", "memory-1", { response: "ignored" })
    );
  });
});
