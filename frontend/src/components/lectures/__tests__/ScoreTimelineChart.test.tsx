/**
 * T-137 — ScoreTimelineChart (version-by-version score timeline).
 * Exercises the four UI states + the pagination acceptance (default last 6,
 * older/newer via page changes). Recharts' internal SVG rendering (the line
 * path, hover tooltip positioning) is not asserted on directly — jsdom has
 * no ResizeObserver/layout engine, which is a well-known limitation for
 * testing chart libraries; a minimal ResizeObserver stub below is just
 * enough for ResponsiveContainer to mount without throwing.
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NextIntlClientProvider, useTranslations } from "next-intl";
import en from "../../../../messages/en/common.json";
import { ScoreTimelineChart } from "../ScoreTimelineChart";
import type { LectureVersionListResponse, LectureVersionRead } from "@/lib/api/types";

class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
// jsdom has no ResizeObserver; Recharts' ResponsiveContainer needs one to mount.
global.ResizeObserver = ResizeObserverStub as unknown as typeof ResizeObserver;

type ListVersionsFn = (
  token: string,
  lectureId: string,
  page?: number,
  pageSize?: number
) => Promise<LectureVersionListResponse>;

function makeVersion(overrides: Partial<LectureVersionRead>): LectureVersionRead {
  return {
    id: `v-${overrides.version}`,
    lecture_id: "lec-1",
    version: 1,
    content_jsonb: null,
    body: "Body.",
    scores_jsonb: null,
    topic_relevance_pct: null,
    originality_score: null,
    edit_summary: null,
    created_at: "2026-08-05T00:00:00Z",
    ...overrides,
  };
}

function makePage(
  versionsDesc: LectureVersionRead[],
  total: number,
  page: number
): LectureVersionListResponse {
  return { items: versionsDesc, total, page, page_size: 6, pages: Math.ceil(total / 6) };
}

function TestWrapper({ listVersions }: { listVersions: ListVersionsFn }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={client}>
      <NextIntlClientProvider locale="en" messages={en}>
        <Inner listVersions={listVersions} />
      </NextIntlClientProvider>
    </QueryClientProvider>
  );
}

function Inner({ listVersions }: { listVersions: ListVersionsFn }) {
  const t = useTranslations("teacher.lectures.wizard");
  return (
    <ScoreTimelineChart
      token="tok"
      lectureId="lec-1"
      api={{ listVersions }}
      t={t}
      queryKeyPrefix="teacher"
    />
  );
}

describe("ScoreTimelineChart", () => {
  it("shows a loading skeleton while versions load", () => {
    const listVersions = vi.fn(() => new Promise<never>(() => {}));
    render(<TestWrapper listVersions={listVersions} />);

    expect(document.querySelectorAll('[class*="animate-pulse"]').length).toBeGreaterThan(0);
  });

  it("shows an error state with retry when versions fail to load", async () => {
    const listVersions = vi.fn().mockRejectedValue(new Error("network error"));
    const user = userEvent.setup();
    render(<TestWrapper listVersions={listVersions} />);

    expect(await screen.findByRole("button", { name: /retry/i })).toBeInTheDocument();
    listVersions.mockResolvedValue(makePage([], 0, 1));
    await user.click(screen.getByRole("button", { name: /retry/i }));
    expect(await screen.findByText(/No scored versions yet/i)).toBeInTheDocument();
  });

  it("shows the empty state when the lecture has no scored versions", async () => {
    const listVersions = vi.fn().mockResolvedValue(makePage([], 0, 1));
    render(<TestWrapper listVersions={listVersions} />);

    expect(await screen.findByText(/No scored versions yet/i)).toBeInTheDocument();
  });

  it("requests the default page size (6) on first render", async () => {
    const listVersions = vi
      .fn()
      .mockResolvedValue(
        makePage([makeVersion({ version: 1, scores_jsonb: { total: 30 } })], 1, 1)
      );
    render(<TestWrapper listVersions={listVersions} />);

    await waitFor(() => expect(listVersions).toHaveBeenCalledWith("tok", "lec-1", 1, 6));
  });

  it("renders the chart heading and pagination controls once data loads", async () => {
    const versions = Array.from({ length: 6 }, (_, i) =>
      makeVersion({ version: 8 - i, scores_jsonb: { total: 30 + (8 - i) } })
    );
    const listVersions = vi.fn().mockResolvedValue(makePage(versions, 8, 1));
    render(<TestWrapper listVersions={listVersions} />);

    expect(await screen.findByText(/Score Timeline/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Older/i })).toBeEnabled();
    expect(screen.getByRole("button", { name: /Newer/i })).toBeDisabled();
  });

  it("clicking Older requests page 2", async () => {
    const user = userEvent.setup();
    const versions = Array.from({ length: 6 }, (_, i) =>
      makeVersion({ version: 8 - i, scores_jsonb: { total: 30 + (8 - i) } })
    );
    const listVersions = vi.fn().mockResolvedValue(makePage(versions, 8, 1));
    render(<TestWrapper listVersions={listVersions} />);

    await screen.findByText(/Score Timeline/i);
    await user.click(screen.getByRole("button", { name: /Older/i }));

    await waitFor(() => expect(listVersions).toHaveBeenCalledWith("tok", "lec-1", 2, 6));
  });

  it("disables Older once the last page is reached", async () => {
    const user = userEvent.setup();
    const page1 = Array.from({ length: 6 }, (_, i) =>
      makeVersion({ version: 8 - i, scores_jsonb: { total: 30 + (8 - i) } })
    );
    const page2 = [
      makeVersion({ version: 2, scores_jsonb: { total: 32 } }),
      makeVersion({ version: 1, scores_jsonb: { total: 31 } }),
    ];
    const listVersions = vi.fn(async (_token: string, _id: string, page = 1) =>
      page === 1 ? makePage(page1, 8, 1) : makePage(page2, 8, 2)
    );
    render(<TestWrapper listVersions={listVersions} />);

    await screen.findByText(/Score Timeline/i);
    await user.click(screen.getByRole("button", { name: /Older/i }));

    await waitFor(() => expect(listVersions).toHaveBeenCalledWith("tok", "lec-1", 2, 6));
    await waitFor(() => expect(screen.getByRole("button", { name: /Older/i })).toBeDisabled());
    expect(screen.getByRole("button", { name: /Newer/i })).toBeEnabled();
  });
});
