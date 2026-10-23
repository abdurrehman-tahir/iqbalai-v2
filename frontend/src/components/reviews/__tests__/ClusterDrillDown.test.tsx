import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactElement } from "react";
import { ClusterDrillDown } from "../ClusterDrillDown";
import { DETAIL, cluster } from "./review-fixtures";

vi.mock("next-intl", () => import("@/test/mocks/next-intl"));
vi.mock("@/hooks/use-client-auth", () => ({
  useClientAuth: () => ({ mounted: true, token: "test-token" }),
}));

const reply = vi.fn();
const skipCluster = vi.fn();
vi.mock("@/lib/api", () => ({
  nextDayReviewApi: {
    reply: (...a: unknown[]) => reply(...a),
    skipCluster: (...a: unknown[]) => skipCluster(...a),
  },
  lectureWizardApi: { transcribeVoice: vi.fn() },
}));

// Stub the canonical widget (own tests) — like the real one it swallows rejections.
vi.mock("@/components/shared/HybridInputWidget", () => ({
  HybridInputWidget: (props: {
    onSubmit: (p: { text: string; attached_images: [] }) => Promise<void>;
  }) => (
    <button
      onClick={() =>
        void props.onSubmit({ text: "See page 12", attached_images: [] }).catch(() => undefined)
      }
    >
      send-reply
    </button>
  ),
}));

function renderWithClient(ui: ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

const CLUSTER = cluster("a", "critical");

beforeEach(() => vi.clearAllMocks());

describe("ClusterDrillDown", () => {
  it("owner sees each student's exact wording with their name and a content link", () => {
    renderWithClient(<ClusterDrillDown review={DETAIL} cluster={CLUSTER} onClose={vi.fn()} />);
    expect(screen.getByTestId("drilldown-student")).toHaveTextContent("Ali");
    expect(screen.getByText("Why a? (Ali)")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "open_content" })).toHaveAttribute(
      "href",
      "/teacher/lectures/lec-1?paragraph=p1",
    );
  });

  it("staff view has no names and no reply/skip controls (aggregate only)", () => {
    const staffCluster = cluster("a", "critical", {
      questions: [{ ...CLUSTER.questions![0], student_user_id: null, student_name: null }],
    });
    renderWithClient(
      <ClusterDrillDown
        review={{ ...DETAIL, is_owner: false, can_act: false }}
        cluster={staffCluster}
        onClose={vi.fn()}
      />,
    );
    expect(screen.queryByTestId("drilldown-student")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /reply/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "skip" })).not.toBeInTheDocument();
  });

  it("replies to a specific student", async () => {
    reply.mockResolvedValue(DETAIL);
    renderWithClient(<ClusterDrillDown review={DETAIL} cluster={CLUSTER} onClose={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: /reply/ }));
    await userEvent.click(screen.getByRole("button", { name: "send-reply" }));
    expect(reply).toHaveBeenCalledWith("test-token", "rev-1", {
      cluster_ref: "a",
      student_user_id: "stu-0",
      body: "See page 12",
    });
  });

  it("skips the cluster", async () => {
    skipCluster.mockResolvedValue(DETAIL);
    renderWithClient(<ClusterDrillDown review={DETAIL} cluster={CLUSTER} onClose={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "skip" }));
    expect(skipCluster).toHaveBeenCalledWith("test-token", "rev-1", { cluster_ref: "a" });
  });

  it("shows sent replies and the skipped badge", () => {
    renderWithClient(
      <ClusterDrillDown
        review={{
          ...DETAIL,
          replies: [
            {
              id: "rep-1",
              review_id: "rev-1",
              cluster_id: "a",
              student_user_id: "stu-0",
              body: "Check the diagram",
              created_at: "2026-10-23T06:10:00Z",
            },
          ],
        }}
        cluster={{ ...CLUSTER, skipped: true }}
        onClose={vi.fn()}
      />,
    );
    expect(screen.getByTestId("drilldown-reply")).toHaveTextContent("Check the diagram");
    expect(screen.getByText("skipped")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "skip" })).not.toBeInTheDocument();
  });

  it("surfaces a failed skip", async () => {
    skipCluster.mockRejectedValue(new Error("500"));
    renderWithClient(<ClusterDrillDown review={DETAIL} cluster={CLUSTER} onClose={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "skip" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("error");
  });
});
