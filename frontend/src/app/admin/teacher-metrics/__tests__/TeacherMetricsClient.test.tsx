import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactElement } from "react";
import { TeacherMetricsClient } from "../TeacherMetricsClient";

vi.mock("next-intl", () => import("@/test/mocks/next-intl"));

vi.mock("@/hooks/use-client-auth", () => ({
  useClientAuth: () => ({ mounted: true, token: "test-token" }),
}));

const listTeacherMetrics = vi.fn();
const exportTeacherMetricsCsv = vi.fn();
vi.mock("@/lib/api", () => ({
  adminMetricsApi: {
    listTeacherMetrics: (...a: unknown[]) => listTeacherMetrics(...a),
    exportTeacherMetricsCsv: (...a: unknown[]) => exportTeacherMetricsCsv(...a),
  },
}));

function renderWithClient(ui: ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

const ROW_A = {
  teacher_user_id: "t-1",
  teacher_name: "Ayesha Khan",
  school_id: "school-1",
  school_name: "Model School",
  subject_id: "subj-1",
  subject_name: "Mathematics",
  grade_range: "9",
  lecture_count: 4,
  avg_originality: 8,
  avg_depth: 7,
  avg_cultural_relevance: 4,
  avg_engagement: 4,
  avg_alignment: 9,
  avg_voice_quality: null,
  avg_ai_learning: 6,
  avg_total: 38,
  avg_topic_relevance_pct: 82,
};

const ROW_B = {
  ...ROW_A,
  teacher_user_id: "t-2",
  teacher_name: "Bilal Ahmed",
  subject_name: "Science",
  avg_total: 60,
  avg_topic_relevance_pct: null,
};

beforeEach(() => {
  vi.clearAllMocks();
  listTeacherMetrics.mockResolvedValue([ROW_A, ROW_B]);
  URL.createObjectURL = vi.fn(() => "blob:mock-url");
  URL.revokeObjectURL = vi.fn();
});

describe("TeacherMetricsClient", () => {
  it("shows a loading skeleton, then the metrics table", async () => {
    renderWithClient(<TeacherMetricsClient />);

    expect(await screen.findByText("Ayesha Khan")).toBeInTheDocument();
    expect(screen.getByText("Bilal Ahmed")).toBeInTheDocument();
  });

  it("shows an error state with retry when metrics fail to load", async () => {
    listTeacherMetrics.mockRejectedValueOnce(new Error("boom"));
    const user = userEvent.setup();
    renderWithClient(<TeacherMetricsClient />);

    expect(await screen.findByRole("button", { name: "retry" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "retry" }));
    expect(await screen.findByText("Ayesha Khan")).toBeInTheDocument();
  });

  it("shows the empty state when there are no rows", async () => {
    listTeacherMetrics.mockResolvedValue([]);
    renderWithClient(<TeacherMetricsClient />);

    expect(await screen.findByText("empty.title")).toBeInTheDocument();
  });

  it("filters rows by the search box across teacher/subject/school", async () => {
    const user = userEvent.setup();
    renderWithClient(<TeacherMetricsClient />);

    await screen.findByText("Ayesha Khan");
    await user.type(screen.getByPlaceholderText("search_placeholder"), "science");

    expect(screen.queryByText("Ayesha Khan")).not.toBeInTheDocument();
    expect(screen.getByText("Bilal Ahmed")).toBeInTheDocument();
  });

  it("sorts rows when a column header is clicked", async () => {
    const user = userEvent.setup();
    renderWithClient(<TeacherMetricsClient />);

    await screen.findByText("Ayesha Khan");
    // Default sort is avg_total desc: Bilal (60) before Ayesha (38).
    let rows = screen.getAllByRole("row").slice(1);
    expect(rows[0]).toHaveTextContent("Bilal Ahmed");

    const sortButton = screen.getByText(/col\.avg_total/).closest("button");
    if (!sortButton) throw new Error("sort button not found");
    await user.click(sortButton);
    rows = screen.getAllByRole("row").slice(1);
    expect(rows[0]).toHaveTextContent("Ayesha Khan");
  });

  it("triggers a CSV export on button click", async () => {
    exportTeacherMetricsCsv.mockResolvedValue(new Blob(["csv"], { type: "text/csv" }));
    const user = userEvent.setup();
    renderWithClient(<TeacherMetricsClient />);

    await screen.findByText("Ayesha Khan");
    await user.click(screen.getByRole("button", { name: "export_csv" }));

    await waitFor(() => expect(exportTeacherMetricsCsv).toHaveBeenCalledWith("test-token"));
  });
});
