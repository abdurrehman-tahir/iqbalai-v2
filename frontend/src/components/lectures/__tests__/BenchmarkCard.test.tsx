/**
 * T-139 — BenchmarkCard (anonymized peer benchmark, Flow 5 §3.11 #37).
 * Exercises the four UI states + the opt-out toggle.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NextIntlClientProvider, useTranslations } from "next-intl";
import en from "../../../../messages/en/common.json";
import { BenchmarkCard } from "../BenchmarkCard";
import type { TeacherBenchmarkRead } from "@/lib/api/types";

const listSuggestions = vi.fn();
const setOptOut = vi.fn();

vi.mock("@/lib/api", () => ({
  teacherBenchmarksApi: {
    list: (...args: unknown[]) => listSuggestions(...args),
    setOptOut: (...args: unknown[]) => setOptOut(...args),
  },
}));

const ROW: TeacherBenchmarkRead = {
  id: "bm-1",
  subject_name: "Mathematics",
  grade_range: "9",
  region: "Punjab",
  top_percent: 23,
};

function TestWrapper() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={client}>
      <NextIntlClientProvider locale="en" messages={en}>
        <Inner />
      </NextIntlClientProvider>
    </QueryClientProvider>
  );
}

function Inner() {
  const t = useTranslations("teacher.lectures.wizard");
  return <BenchmarkCard token="tok" t={t} queryKeyPrefix="teacher" />;
}

describe("BenchmarkCard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows a loading skeleton while benchmarks load", () => {
    listSuggestions.mockReturnValue(new Promise<never>(() => {}));
    const { container } = render(<TestWrapper />);

    expect(container.querySelectorAll('[class*="animate-pulse"]').length).toBeGreaterThan(0);
  });

  it("shows an error state with retry when benchmarks fail to load", async () => {
    listSuggestions.mockRejectedValue(new Error("network error"));
    const user = userEvent.setup();
    render(<TestWrapper />);

    expect(await screen.findByRole("button", { name: /retry/i })).toBeInTheDocument();
    listSuggestions.mockResolvedValue([]);
    await user.click(screen.getByRole("button", { name: /retry/i }));
    await waitFor(() => expect(listSuggestions).toHaveBeenCalledTimes(2));
  });

  it("shows an empty message when there is no benchmark data yet", async () => {
    listSuggestions.mockResolvedValue([]);
    render(<TestWrapper />);

    expect(
      await screen.findByText(/Not enough peer data yet to show your standing/i)
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Stop comparing me to peers/i })).toBeInTheDocument();
  });

  it("renders the positively-framed top-percent line for each row", async () => {
    listSuggestions.mockResolvedValue([ROW]);
    render(<TestWrapper />);

    expect(
      await screen.findByText("Top 23% of Mathematics teachers in Punjab")
    ).toBeInTheDocument();
  });

  it("opting out calls setOptOut with true and flips the button label", async () => {
    listSuggestions.mockResolvedValue([ROW]);
    setOptOut.mockResolvedValue({ rows_changed: 1 });
    const user = userEvent.setup();
    render(<TestWrapper />);

    await user.click(await screen.findByRole("button", { name: /Stop comparing me to peers/i }));

    await waitFor(() =>
      expect(setOptOut).toHaveBeenCalledWith("tok", { opted_out: true })
    );
    expect(
      await screen.findByRole("button", { name: /Resume peer comparison/i })
    ).toBeInTheDocument();
  });
});
