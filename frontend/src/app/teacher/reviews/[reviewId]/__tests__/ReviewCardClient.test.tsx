import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactElement } from "react";
import { COLUMN_LIMIT, ReviewCardClient } from "../ReviewCardClient";
import { DETAIL, cluster } from "@/components/reviews/__tests__/review-fixtures";

vi.mock("next-intl", () => import("@/test/mocks/next-intl"));
vi.mock("@/hooks/use-client-auth", () => ({
  useClientAuth: () => ({ mounted: true, token: "test-token" }),
}));

const get = vi.fn();
vi.mock("@/lib/api", () => ({
  nextDayReviewApi: { get: (...a: unknown[]) => get(...a) },
}));

function renderWithClient(ui: ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

beforeEach(() => vi.clearAllMocks());

describe("ReviewCardClient", () => {
  it("shows the loading skeleton", () => {
    get.mockReturnValue(new Promise(() => {}));
    renderWithClient(<ReviewCardClient reviewId="rev-1" />);
    expect(screen.getByTestId("review-loading")).toBeInTheDocument();
  });

  it("shows an error state with retry", async () => {
    get.mockRejectedValue(new Error("nope"));
    renderWithClient(<ReviewCardClient reviewId="rev-1" />);
    expect(await screen.findByText("card.error")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "card.retry" })).toBeInTheDocument();
  });

  it("renders the locked layout: summary, critical, frequent, mini preview", async () => {
    get.mockResolvedValue(DETAIL);
    renderWithClient(<ReviewCardClient reviewId="rev-1" />);
    expect(await screen.findByTestId("review-card")).toBeInTheDocument();
    expect(screen.getByTestId("review-summary")).toHaveTextContent(DETAIL.ai_summary);
    expect(within(screen.getByTestId("review-critical")).getByText("Why a?")).toBeInTheDocument();
    expect(within(screen.getByTestId("review-frequent")).getByText("Why b?")).toBeInTheDocument();
    const mini = screen.getByTestId("review-mini");
    expect(within(mini).getByText(DETAIL.mini_preview!)).toBeInTheDocument();
    expect(within(mini).getByRole("link", { name: "mini_open" })).toHaveAttribute(
      "href",
      "/teacher/lectures/mini-1",
    );
  });

  it("empty columns and a missing summary/mini still render (partial review)", async () => {
    get.mockResolvedValue({
      ...DETAIL,
      ai_summary: "",
      critical: [],
      mini_lecture_id: null,
      mini_preview: null,
    });
    renderWithClient(<ReviewCardClient reviewId="rev-1" />);
    expect(await screen.findByText("card.summary_empty")).toBeInTheDocument();
    expect(screen.getByText("column_empty")).toBeInTheDocument();
    expect(screen.getByText("mini_none")).toBeInTheDocument();
  });

  it("caps each column at the top 10 with an 'and N more' expander", async () => {
    const many = Array.from({ length: COLUMN_LIMIT + 2 }, (_, i) =>
      cluster(`c${i}`, "high_frequency"),
    );
    get.mockResolvedValue({ ...DETAIL, high_frequency: many });
    renderWithClient(<ReviewCardClient reviewId="rev-1" />);
    const column = await screen.findByTestId("review-frequent");
    expect(within(column).getAllByTestId("review-cluster")).toHaveLength(COLUMN_LIMIT);
    await userEvent.click(within(column).getByRole("button", { name: "more" }));
    expect(within(column).getAllByTestId("review-cluster")).toHaveLength(COLUMN_LIMIT + 2);
  });
});
