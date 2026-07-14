import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FrameworksClient } from "../FrameworksClient";
import { renderWithQuery } from "@/test/helpers/render-admin";

vi.mock("next-intl", () => import("@/test/mocks/next-intl"));
vi.mock("@/hooks/use-client-auth", () => ({
  useClientAuth: () => ({ mounted: true, token: "tok" }),
}));

const mockList = vi.fn();
const mockTriggerResearch = vi.fn();
const mockLatestResearch = vi.fn();
const mockReviewPlan = vi.fn();
const mockApprove = vi.fn();
const mockReject = vi.fn();
const mockRefresh = vi.fn();
const mockDeprecate = vi.fn();
vi.mock("@/lib/api", () => ({
  ApiError: class ApiError extends Error {},
  frameworksApi: {
    list: (...a: unknown[]) => mockList(...a),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
    triggerResearch: (...a: unknown[]) => mockTriggerResearch(...a),
    latestResearch: (...a: unknown[]) => mockLatestResearch(...a),
    reviewPlan: (...a: unknown[]) => mockReviewPlan(...a),
    approve: (...a: unknown[]) => mockApprove(...a),
    reject: (...a: unknown[]) => mockReject(...a),
    refresh: (...a: unknown[]) => mockRefresh(...a),
    deprecate: (...a: unknown[]) => mockDeprecate(...a),
  },
}));

beforeEach(() => vi.clearAllMocks());

const DRAFT_FRAMEWORK = {
  id: "fw1",
  name: "Matric Punjab — Physics",
  exam_target: "Matric Punjab Board — Physics",
  region: "Punjab",
  target_grade_range: [9, 10],
  language: "en",
  status: "draft",
  created_by: "admin-1",
  created_at: "2026-01-01T00:00:00Z",
};

describe("FrameworksClient — four UI states (T-092)", () => {
  it("loading shows heading", () => {
    mockList.mockReturnValue(new Promise(() => {}));
    renderWithQuery(<FrameworksClient />);
    expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
  });

  it("error shows error message", async () => {
    mockList.mockRejectedValue(new Error("x"));
    renderWithQuery(<FrameworksClient />);
    await waitFor(() => expect(screen.getByText("error")).toBeInTheDocument());
  });

  it("empty shows empty state", async () => {
    mockList.mockResolvedValue([]);
    renderWithQuery(<FrameworksClient />);
    await waitFor(() => expect(screen.getByText("empty.title")).toBeInTheDocument());
  });

  it("success lists frameworks", async () => {
    mockList.mockResolvedValue([DRAFT_FRAMEWORK]);
    renderWithQuery(<FrameworksClient />);
    await waitFor(() => expect(screen.getByText("Matric Punjab — Physics")).toBeInTheDocument());
  });
});

describe("FrameworksClient — AI research (T-093)", () => {
  it("triggers research on a DRAFT framework", async () => {
    mockList.mockResolvedValue([DRAFT_FRAMEWORK]);
    mockTriggerResearch.mockResolvedValue({
      id: "job1",
      framework_id: "fw1",
      status: "running",
      cost_usd: 0,
      sources_count: 0,
      error: null,
      study_plan_id: null,
      started_at: "2026-01-01T00:00:00Z",
      finished_at: null,
      created_at: "2026-01-01T00:00:00Z",
    });
    renderWithQuery(<FrameworksClient />);
    await waitFor(() => expect(screen.getByText("Matric Punjab — Physics")).toBeInTheDocument());

    await userEvent.click(screen.getByRole("button", { name: "actions.research" }));
    await waitFor(() => expect(mockTriggerResearch).toHaveBeenCalledWith("tok", "fw1"));
  });

  it("opens the research panel for a non-DRAFT framework and shows the job", async () => {
    mockList.mockResolvedValue([{ ...DRAFT_FRAMEWORK, status: "pending_approval" }]);
    mockLatestResearch.mockResolvedValue({
      id: "job1",
      framework_id: "fw1",
      status: "succeeded",
      cost_usd: 2.5,
      sources_count: 8,
      error: null,
      study_plan_id: "plan1",
      started_at: "2026-01-01T00:00:00Z",
      finished_at: "2026-01-01T00:05:00Z",
      created_at: "2026-01-01T00:00:00Z",
    });
    renderWithQuery(<FrameworksClient />);
    await waitFor(() => expect(screen.getByText("Matric Punjab — Physics")).toBeInTheDocument());

    await userEvent.click(screen.getByRole("button", { name: "actions.view_research" }));
    await waitFor(() => expect(mockLatestResearch).toHaveBeenCalledWith("tok", "fw1"));
    await waitFor(() => expect(screen.getByText("$2.50")).toBeInTheDocument());
  });

  it("research panel shows empty state when no job exists (404)", async () => {
    mockList.mockResolvedValue([{ ...DRAFT_FRAMEWORK, status: "researching" }]);
    mockLatestResearch.mockRejectedValue(new Error("not found"));
    renderWithQuery(<FrameworksClient />);
    await waitFor(() => expect(screen.getByText("Matric Punjab — Physics")).toBeInTheDocument());

    await userEvent.click(screen.getByRole("button", { name: "actions.view_research" }));
    await waitFor(() => expect(screen.getByText("research_modal.empty_title")).toBeInTheDocument());
  });
});

const PENDING_FRAMEWORK = { ...DRAFT_FRAMEWORK, status: "pending_approval" };
const PENDING_PLAN = {
  id: "plan1",
  framework_id: "fw1",
  version: 2,
  content_jsonb: {
    topics: [{ topic_name: "Kinematics" }, { topic_name: "Dynamics" }],
    weekly_pacing: [{}, {}, {}],
    exam_strategy: {},
  },
  sources_cited_jsonb: [{ url: "https://ex.com", title: "Past papers" }],
  generated_at: "2026-01-01T00:00:00Z",
  approved_by: null,
  approved_at: null,
  status: "pending_approval",
  reviewer_notes: null,
  created_at: "2026-01-01T00:00:00Z",
};

describe("FrameworksClient — approval review (T-094)", () => {
  it("review action is only offered for a pending-approval framework", async () => {
    mockList.mockResolvedValue([DRAFT_FRAMEWORK]);
    renderWithQuery(<FrameworksClient />);
    await waitFor(() => expect(screen.getByText("Matric Punjab — Physics")).toBeInTheDocument());
    expect(screen.queryByRole("button", { name: "actions.review" })).not.toBeInTheDocument();
  });

  it("opens the review panel and shows plan content + cited sources", async () => {
    mockList.mockResolvedValue([PENDING_FRAMEWORK]);
    mockReviewPlan.mockResolvedValue(PENDING_PLAN);
    renderWithQuery(<FrameworksClient />);
    await waitFor(() => expect(screen.getByText("Matric Punjab — Physics")).toBeInTheDocument());

    await userEvent.click(screen.getByRole("button", { name: "actions.review" }));
    await waitFor(() => expect(mockReviewPlan).toHaveBeenCalledWith("tok", "fw1"));
    await waitFor(() => expect(screen.getByText("Kinematics")).toBeInTheDocument());
    expect(screen.getByText("Past papers")).toBeInTheDocument();
  });

  it("approves the plan", async () => {
    mockList.mockResolvedValue([PENDING_FRAMEWORK]);
    mockReviewPlan.mockResolvedValue(PENDING_PLAN);
    mockApprove.mockResolvedValue({ ...PENDING_PLAN, status: "approved" });
    renderWithQuery(<FrameworksClient />);
    await waitFor(() => expect(screen.getByText("Matric Punjab — Physics")).toBeInTheDocument());

    await userEvent.click(screen.getByRole("button", { name: "actions.review" }));
    await waitFor(() => expect(screen.getByText("Kinematics")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: "review_modal.approve" }));
    await waitFor(() => expect(mockApprove).toHaveBeenCalledWith("tok", "fw1"));
  });

  it("rejects the plan with reviewer notes", async () => {
    mockList.mockResolvedValue([PENDING_FRAMEWORK]);
    mockReviewPlan.mockResolvedValue(PENDING_PLAN);
    mockReject.mockResolvedValue({ ...PENDING_PLAN, status: "draft" });
    renderWithQuery(<FrameworksClient />);
    await waitFor(() => expect(screen.getByText("Matric Punjab — Physics")).toBeInTheDocument());

    await userEvent.click(screen.getByRole("button", { name: "actions.review" }));
    await waitFor(() => expect(screen.getByText("Kinematics")).toBeInTheDocument());

    await userEvent.click(screen.getByRole("button", { name: "review_modal.reject" }));
    await userEvent.type(
      screen.getByLabelText("review_modal.notes_label", { exact: false }),
      "Topic weights look off; re-run research.",
    );
    await userEvent.click(screen.getByRole("button", { name: "review_modal.confirm_reject" }));
    await waitFor(() =>
      expect(mockReject).toHaveBeenCalledWith("tok", "fw1", {
        notes: "Topic weights look off; re-run research.",
      }),
    );
  });

  it("shows empty state when no plan is pending (404)", async () => {
    mockList.mockResolvedValue([PENDING_FRAMEWORK]);
    mockReviewPlan.mockRejectedValue(new Error("not found"));
    renderWithQuery(<FrameworksClient />);
    await waitFor(() => expect(screen.getByText("Matric Punjab — Physics")).toBeInTheDocument());

    await userEvent.click(screen.getByRole("button", { name: "actions.review" }));
    await waitFor(() =>
      expect(screen.getByText("review_modal.empty_title")).toBeInTheDocument(),
    );
  });
});

const PUBLISHED_FRAMEWORK = { ...DRAFT_FRAMEWORK, status: "published" };

describe("FrameworksClient — versioning + refresh + deprecate (T-095)", () => {
  it("refresh/deprecate actions are only offered for a PUBLISHED framework", async () => {
    mockList.mockResolvedValue([DRAFT_FRAMEWORK]);
    renderWithQuery(<FrameworksClient />);
    await waitFor(() => expect(screen.getByText("Matric Punjab — Physics")).toBeInTheDocument());
    expect(screen.queryByRole("button", { name: "actions.refresh" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "actions.deprecate" })).not.toBeInTheDocument();
  });

  it("triggers a refresh on a PUBLISHED framework", async () => {
    mockList.mockResolvedValue([PUBLISHED_FRAMEWORK]);
    mockRefresh.mockResolvedValue({
      id: "job2",
      framework_id: "fw1",
      status: "running",
      cost_usd: 0,
      sources_count: 0,
      error: null,
      study_plan_id: null,
      started_at: "2026-01-01T00:00:00Z",
      finished_at: null,
      created_at: "2026-01-01T00:00:00Z",
    });
    renderWithQuery(<FrameworksClient />);
    await waitFor(() => expect(screen.getByText("Matric Punjab — Physics")).toBeInTheDocument());

    await userEvent.click(screen.getByRole("button", { name: "actions.refresh" }));
    await waitFor(() => expect(mockRefresh).toHaveBeenCalledWith("tok", "fw1"));
  });

  it("deprecates a PUBLISHED framework after confirmation", async () => {
    mockList.mockResolvedValue([PUBLISHED_FRAMEWORK]);
    mockDeprecate.mockResolvedValue({ ...PUBLISHED_FRAMEWORK, status: "deprecated" });
    renderWithQuery(<FrameworksClient />);
    await waitFor(() => expect(screen.getByText("Matric Punjab — Physics")).toBeInTheDocument());

    await userEvent.click(screen.getByRole("button", { name: "actions.deprecate" }));
    await waitFor(() =>
      expect(screen.getByText("deprecate_modal.title")).toBeInTheDocument(),
    );
    await userEvent.click(screen.getByRole("button", { name: "deprecate_modal.confirm" }));
    await waitFor(() => expect(mockDeprecate).toHaveBeenCalledWith("tok", "fw1"));
  });
});
