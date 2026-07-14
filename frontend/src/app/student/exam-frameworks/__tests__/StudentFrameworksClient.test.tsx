import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NextIntlClientProvider } from "next-intl";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { StudentFrameworksClient } from "../StudentFrameworksClient";
import en from "../../../../../messages/en/common.json";

vi.mock("@/hooks/use-client-auth", () => ({
  useClientAuth: () => ({ mounted: true, token: "tok" }),
}));

const mockAvailable = vi.fn();
const mockSelections = vi.fn();
const mockSelect = vi.fn();
const mockStudyPlan = vi.fn();
const mockSwitch = vi.fn();
const mockDrop = vi.fn();

vi.mock("@/lib/api", () => ({
  ApiError: class ApiError extends Error {},
  studentFrameworksApi: {
    available: (...a: unknown[]) => mockAvailable(...a),
    selections: (...a: unknown[]) => mockSelections(...a),
    select: (...a: unknown[]) => mockSelect(...a),
    studyPlan: (...a: unknown[]) => mockStudyPlan(...a),
    switchVersion: (...a: unknown[]) => mockSwitch(...a),
    drop: (...a: unknown[]) => mockDrop(...a),
  },
}));

beforeEach(() => vi.clearAllMocks());

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <NextIntlClientProvider locale="en" messages={en}>
        <StudentFrameworksClient />
      </NextIntlClientProvider>
    </QueryClientProvider>,
  );
}

const SELECTION = {
  id: "sel-1",
  framework_id: "fw-1",
  framework_name: "Matric Punjab — Physics",
  exam_target: "Matric Punjab Board — Physics",
  pinned_version: 1,
  latest_version: 1,
  update_available: false,
  status: "active",
  selected_at: "2026-01-01T00:00:00Z",
};

const AVAILABLE = {
  id: "fw-2",
  name: "NTS Scholarship",
  exam_target: "NTS",
  region: "Punjab",
  target_grade_range: [10],
  language: "en",
  current_version: 1,
};

describe("StudentFrameworksClient (T-096)", () => {
  it("shows empty state when the student has no selections", async () => {
    mockSelections.mockResolvedValue([]);
    renderPage();
    await waitFor(() =>
      expect(screen.getByText(en.student.frameworks.my_empty_title)).toBeInTheDocument(),
    );
  });

  it("lists selections and renders the opt-in update banner", async () => {
    mockSelections.mockResolvedValue([
      { ...SELECTION, pinned_version: 1, latest_version: 2, update_available: true },
    ]);
    renderPage();
    await waitFor(() =>
      expect(screen.getByText("Matric Punjab — Physics")).toBeInTheDocument(),
    );
    expect(screen.getByRole("button", { name: en.student.frameworks.switch })).toBeInTheDocument();
  });

  it("switches to the latest version when the student opts in", async () => {
    mockSelections.mockResolvedValue([
      { ...SELECTION, pinned_version: 1, latest_version: 2, update_available: true },
    ]);
    mockSwitch.mockResolvedValue({ ...SELECTION, pinned_version: 2, update_available: false });
    renderPage();
    await waitFor(() => expect(screen.getByText("Matric Punjab — Physics")).toBeInTheDocument());

    await userEvent.click(screen.getByRole("button", { name: en.student.frameworks.switch }));
    await waitFor(() => expect(mockSwitch).toHaveBeenCalledWith("tok", "sel-1"));
  });

  it("browses and selects a framework scoped by region + grade", async () => {
    mockSelections.mockResolvedValue([]);
    mockAvailable.mockResolvedValue([AVAILABLE]);
    mockSelect.mockResolvedValue({ ...SELECTION, id: "sel-2", framework_id: "fw-2" });
    renderPage();
    await waitFor(() =>
      expect(screen.getByText(en.student.frameworks.my_empty_title)).toBeInTheDocument(),
    );

    await userEvent.type(screen.getByLabelText(en.student.frameworks.region_label), "Punjab");
    await userEvent.type(screen.getByLabelText(en.student.frameworks.grade_label), "10");
    await userEvent.click(screen.getByRole("button", { name: en.student.frameworks.browse_button }));

    await waitFor(() => expect(mockAvailable).toHaveBeenCalledWith("tok", "Punjab", 10));
    await waitFor(() => expect(screen.getByText("NTS Scholarship")).toBeInTheDocument());

    await userEvent.click(screen.getByRole("button", { name: en.student.frameworks.select }));
    await waitFor(() => expect(mockSelect).toHaveBeenCalledWith("tok", "fw-2"));
  });

  it("opens the study-plan modal and renders topics", async () => {
    mockSelections.mockResolvedValue([SELECTION]);
    mockStudyPlan.mockResolvedValue({
      framework_id: "fw-1",
      framework_name: "Matric Punjab — Physics",
      exam_target: "Matric Punjab Board — Physics",
      version: 1,
      content_jsonb: {
        topics: [{ topic_name: "Kinematics", priority_weight: 0.9 }],
        weekly_pacing: [{}, {}],
        exam_strategy: {},
      },
      generated_at: "2026-01-01T00:00:00Z",
    });
    renderPage();
    await waitFor(() => expect(screen.getByText("Matric Punjab — Physics")).toBeInTheDocument());

    await userEvent.click(screen.getByRole("button", { name: en.student.frameworks.view_plan }));
    await waitFor(() => expect(mockStudyPlan).toHaveBeenCalledWith("tok", "sel-1"));
    await waitFor(() => expect(screen.getByText("Kinematics")).toBeInTheDocument());
  });

  it("drops a selection", async () => {
    mockSelections.mockResolvedValue([SELECTION]);
    mockDrop.mockResolvedValue({ ...SELECTION, status: "abandoned" });
    renderPage();
    await waitFor(() => expect(screen.getByText("Matric Punjab — Physics")).toBeInTheDocument());

    await userEvent.click(screen.getByRole("button", { name: en.student.frameworks.drop }));
    await waitFor(() => expect(mockDrop).toHaveBeenCalledWith("tok", "sel-1"));
  });
});
