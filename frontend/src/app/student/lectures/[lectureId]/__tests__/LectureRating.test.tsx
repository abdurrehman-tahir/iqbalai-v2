/** T-192 — completion signal + optional, dismissable 1–5 rating prompt. */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NextIntlClientProvider } from "next-intl";
import enMessages from "../../../../../../messages/en/common.json";
import { dismissKey, LectureRatingPrompt } from "../LectureRatingPrompt";
import {
  COMPLETION_THRESHOLD,
  hasReachedCompletion,
} from "../use-lecture-completion";

const getMine = vi.fn();
const submit = vi.fn();

vi.mock("@/lib/api", () => ({
  lectureRatingApi: {
    getMine: (...a: unknown[]) => getMine(...a),
    submit: (...a: unknown[]) => submit(...a),
  },
}));
vi.mock("@/hooks/use-client-auth", () => ({
  useClientAuth: () => ({ mounted: true, token: "tok" }),
}));

function renderPrompt(completed: boolean) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <NextIntlClientProvider locale="en" messages={enMessages}>
        <LectureRatingPrompt lectureId="lec-1" completed={completed} />
      </NextIntlClientProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  getMine.mockReset();
  submit.mockReset();
  sessionStorage.clear();
  getMine.mockResolvedValue({ lecture_id: "lec-1", rating: null });
  submit.mockImplementation((_t, _l, body: { rating: number }) =>
    Promise.resolve({ lecture_id: "lec-1", rating: body.rating }),
  );
});

describe("hasReachedCompletion (≥80% or end reached)", () => {
  it("is false before 80% of the lecture has been on screen", () => {
    expect(hasReachedCompletion({ top: 0, height: 1000 }, 700)).toBe(false);
  });
  it("is true once 80% has scrolled into view", () => {
    expect(hasReachedCompletion({ top: -200, height: 1000 }, 600)).toBe(true);
  });
  it("is true when the end is on screen", () => {
    expect(hasReachedCompletion({ top: -900, height: 1000 }, 800)).toBe(true);
  });
  it("uses an 80% threshold", () => {
    expect(COMPLETION_THRESHOLD).toBe(0.8);
    expect(hasReachedCompletion({ top: 0, height: 1000 }, 799)).toBe(false);
    expect(hasReachedCompletion({ top: 0, height: 1000 }, 800)).toBe(true);
  });
  it("ignores empty layouts", () => {
    expect(hasReachedCompletion({ top: 0, height: 0 }, 800)).toBe(false);
  });
});

describe("LectureRatingPrompt", () => {
  it("is not shown before completion (and does not even fetch)", () => {
    renderPrompt(false);
    expect(
      screen.queryByTestId("lecture-rating-prompt"),
    ).not.toBeInTheDocument();
    expect(getMine).not.toHaveBeenCalled();
  });

  it("appears on completion; student picks stars and submits 1-5", async () => {
    renderPrompt(true);
    expect(
      await screen.findByTestId("lecture-rating-prompt"),
    ).toBeInTheDocument();
    const submitBtn = screen.getByTestId("lecture-rating-submit");
    expect(submitBtn).toBeDisabled();

    fireEvent.click(screen.getByRole("radio", { name: "4 stars" }));
    expect(screen.getByRole("radio", { name: "4 stars" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    fireEvent.click(submitBtn);

    await waitFor(() =>
      expect(submit).toHaveBeenCalledWith("tok", "lec-1", { rating: 4 }),
    );
    expect(
      await screen.findByText("Thanks for your rating!"),
    ).toBeInTheDocument();
  });

  it("offers exactly five stars, each a 44px target", async () => {
    renderPrompt(true);
    await screen.findByTestId("lecture-rating-prompt");
    const stars = screen.getAllByRole("radio");
    expect(stars).toHaveLength(5);
    for (const star of stars) expect(star.className).toContain("size-11");
  });

  it("is dismissable and stays dismissed for the lecture", async () => {
    renderPrompt(true);
    fireEvent.click(await screen.findByTestId("lecture-rating-dismiss"));
    expect(
      screen.queryByTestId("lecture-rating-prompt"),
    ).not.toBeInTheDocument();
    expect(sessionStorage.getItem(dismissKey("lec-1"))).toBe("1");
    expect(submit).not.toHaveBeenCalled();
  });

  it("is not shown again once already rated", async () => {
    getMine.mockResolvedValue({ lecture_id: "lec-1", rating: 3 });
    renderPrompt(true);
    await waitFor(() => expect(getMine).toHaveBeenCalled());
    expect(
      screen.queryByTestId("lecture-rating-prompt"),
    ).not.toBeInTheDocument();
  });

  it("surfaces a submit error", async () => {
    submit.mockRejectedValueOnce(new Error("down"));
    renderPrompt(true);
    fireEvent.click(await screen.findByRole("radio", { name: "2 stars" }));
    fireEvent.click(screen.getByTestId("lecture-rating-submit"));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Couldn't save your rating.",
    );
  });

  it("tells the student the rating is anonymous and not graded", async () => {
    renderPrompt(true);
    expect(
      await screen.findByText(/anonymous and never affects your grades/),
    ).toBeInTheDocument();
  });
});
