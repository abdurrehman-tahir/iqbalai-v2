import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LectureDetailClient } from "../LectureDetailClient";

vi.mock("next-intl", () => import("@/test/mocks/next-intl"));
vi.mock("@/hooks/use-client-auth", () => ({
  useClientAuth: () => ({ mounted: true, token: "test-token" }),
}));
vi.mock("@/lib/api", () => ({ lectureWizardApi: {} }));
vi.mock("@/components/lectures/LectureEditorPanel", () => ({
  LectureEditorPanel: ({ lectureId }: { lectureId: string }) => (
    <div data-testid="editor-panel">{lectureId}</div>
  ),
}));
vi.mock("@/components/reviews/ReviewsList", () => ({
  ReviewsList: ({ lectureId }: { lectureId?: string }) => (
    <div data-testid="reviews-list-stub">{lectureId}</div>
  ),
}));

describe("LectureDetailClient", () => {
  it("opens in edit mode with the review context banner", () => {
    render(<LectureDetailClient lectureId="lec-1" fromReviewId="rev-1" initialTab="edit" />);
    expect(screen.getByTestId("editor-panel")).toHaveTextContent("lec-1");
    expect(screen.getByTestId("from-review-banner")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "back_to_review" })).toHaveAttribute(
      "href",
      "/teacher/reviews/rev-1",
    );
  });

  it("has no banner when not opened from a review", () => {
    render(<LectureDetailClient lectureId="lec-1" fromReviewId={null} initialTab="edit" />);
    expect(screen.queryByTestId("from-review-banner")).not.toBeInTheDocument();
  });

  it("switches to the lecture's Reviews tab", async () => {
    render(<LectureDetailClient lectureId="lec-1" fromReviewId={null} initialTab="edit" />);
    await userEvent.click(screen.getByRole("tab", { name: "tab_reviews" }));
    expect(screen.getByTestId("reviews-list-stub")).toHaveTextContent("lec-1");
    expect(screen.getByRole("tab", { name: "tab_reviews" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });
});
