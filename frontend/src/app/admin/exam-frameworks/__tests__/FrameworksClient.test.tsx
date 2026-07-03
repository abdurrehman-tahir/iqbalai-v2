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
vi.mock("@/lib/api", () => ({
  ApiError: class ApiError extends Error {},
  frameworksApi: {
    list: (...a: unknown[]) => mockList(...a),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
    triggerResearch: (...a: unknown[]) => mockTriggerResearch(...a),
    latestResearch: (...a: unknown[]) => mockLatestResearch(...a),
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
