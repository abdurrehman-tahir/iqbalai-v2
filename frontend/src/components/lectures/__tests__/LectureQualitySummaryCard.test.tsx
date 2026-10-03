/** T-192 — teacher sees only the anonymous aggregate + blended quality score. */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NextIntlClientProvider } from "next-intl";
import type { LectureRatingSummaryRead } from "@/lib/api";
import enMessages from "../../../../messages/en/common.json";
import { LectureQualitySummaryCard } from "../LectureQualitySummaryCard";

const summary = vi.fn();
vi.mock("@/lib/api", () => ({
  lectureRatingApi: { summary: (...a: unknown[]) => summary(...a) },
}));

function data(
  overrides: Partial<LectureRatingSummaryRead> = {},
): LectureRatingSummaryRead {
  return {
    lecture_id: "lec-1",
    rating_count: 3,
    min_ratings_for_display: 3,
    average_rating: 4.5,
    ai_score: 44,
    ai_score_max: 55,
    quality_score: 80.9,
    rating_weight: 0.05,
    ...overrides,
  };
}

function renderCard() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <NextIntlClientProvider locale="en" messages={enMessages}>
        <LectureQualitySummaryCard token="tok" lectureId="lec-1" />
      </NextIntlClientProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => summary.mockReset());

describe("LectureQualitySummaryCard", () => {
  it("loading", async () => {
    // Resolve before the test ends: a forever-pending query left mounted here
    // stalled the next test in this file.
    let resolve: (value: LectureRatingSummaryRead) => void = () => undefined;
    summary.mockReturnValue(
      new Promise<LectureRatingSummaryRead>((r) => (resolve = r)),
    );
    renderCard();
    expect(screen.getByTestId("lecture-quality-loading")).toBeInTheDocument();
    resolve(data());
    expect(
      await screen.findByTestId("lecture-quality-score"),
    ).toBeInTheDocument();
  });

  it("error with retry", async () => {
    summary.mockRejectedValueOnce(new Error("x"));
    summary.mockResolvedValue(data());
    renderCard();
    fireEvent.click(await screen.findByRole("button", { name: "Try again" }));
    expect(
      await screen.findByTestId("lecture-quality-score"),
    ).toHaveTextContent("80.9 / 100");
  });

  it("shows blended score, AI score, anonymous average and the 5% weighting", async () => {
    summary.mockResolvedValue(data());
    renderCard();
    expect(
      await screen.findByTestId("lecture-quality-score"),
    ).toHaveTextContent("80.9 / 100");
    expect(screen.getByTestId("lecture-quality-ai")).toHaveTextContent(
      "AI score: 44 / 55",
    );
    expect(screen.getByTestId("lecture-quality-rating")).toHaveTextContent(
      "Student rating: 4.5 / 5 (3 ratings)",
    );
    expect(screen.getByText(/count for 5% of the score/)).toBeInTheDocument();
  });

  it("withholds the average below the anonymity threshold", async () => {
    summary.mockResolvedValue(
      data({ rating_count: 1, average_rating: null, quality_score: 80 }),
    );
    renderCard();
    expect(
      await screen.findByTestId("lecture-quality-rating"),
    ).toHaveTextContent(
      "1 student rating — the average appears once 3 students have rated",
    );
  });

  it("empty: no ratings yet", async () => {
    summary.mockResolvedValue(data({ rating_count: 0, average_rating: null }));
    renderCard();
    expect(
      await screen.findByText("No student ratings yet."),
    ).toBeInTheDocument();
  });
});
