import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactElement } from "react";
import { ReviewsList, reviewStatusKey } from "../ReviewsList";
import { SUMMARY } from "./review-fixtures";
import type { ReviewSummaryRead } from "@/lib/api";

vi.mock("next-intl", () => import("@/test/mocks/next-intl"));
vi.mock("@/hooks/use-client-auth", () => ({
  useClientAuth: () => ({ mounted: true, token: "test-token" }),
}));

const list = vi.fn();
vi.mock("@/lib/api", () => ({
  nextDayReviewApi: { list: (...a: unknown[]) => list(...a) },
}));

function renderWithClient(ui: ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

beforeEach(() => vi.clearAllMocks());

describe("ReviewsList", () => {
  it("shows the loading skeleton first", () => {
    list.mockReturnValue(new Promise(() => {}));
    renderWithClient(<ReviewsList />);
    expect(screen.getByTestId("reviews-loading")).toBeInTheDocument();
  });

  it("shows the 'No review today' empty state", async () => {
    list.mockResolvedValue([]);
    renderWithClient(<ReviewsList />);
    expect(await screen.findByText("list.empty_title")).toBeInTheDocument();
  });

  it("shows an error state with retry", async () => {
    list.mockRejectedValue(new Error("boom"));
    renderWithClient(<ReviewsList />);
    expect(await screen.findByText("list.error")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "list.retry" })).toBeInTheDocument();
  });

  it("renders review rows linking to the card and passes the lecture filter", async () => {
    list.mockResolvedValue([SUMMARY]);
    renderWithClient(<ReviewsList lectureId="lec-1" />);
    const link = await screen.findByRole("link", { name: /Grade 9 Physics/ });
    expect(link).toHaveAttribute("href", "/teacher/reviews/rev-1");
    await waitFor(() => expect(list).toHaveBeenCalledWith("test-token", "lec-1"));
    expect(screen.getByText("status.pending")).toBeInTheDocument();
  });
});

describe("reviewStatusKey", () => {
  const statuses: ReviewSummaryRead["status"][] = ["pending", "completed", "dismissed"];
  it.each(statuses)("maps %s to its own key", (status) => {
    expect(reviewStatusKey({ status, read_only: false })).toBe(status);
  });
  it("read-only wins over status", () => {
    expect(reviewStatusKey({ status: "pending", read_only: true })).toBe("read_only");
  });
});
