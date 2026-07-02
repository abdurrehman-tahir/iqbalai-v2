import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { FrameworksClient } from "../FrameworksClient";
import { renderWithQuery } from "@/test/helpers/render-admin";

vi.mock("next-intl", () => import("@/test/mocks/next-intl"));
vi.mock("@/hooks/use-client-auth", () => ({
  useClientAuth: () => ({ mounted: true, token: "tok" }),
}));

const mockList = vi.fn();
vi.mock("@/lib/api", () => ({
  ApiError: class ApiError extends Error {},
  frameworksApi: {
    list: (...a: unknown[]) => mockList(...a),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
  },
}));

beforeEach(() => vi.clearAllMocks());

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
    mockList.mockResolvedValue([
      {
        id: "fw1",
        name: "Matric Punjab — Physics",
        exam_target: "Matric Punjab Board — Physics",
        region: "Punjab",
        target_grade_range: [9, 10],
        language: "en",
        status: "draft",
        created_by: "admin-1",
        created_at: "2026-01-01T00:00:00Z",
      },
    ]);
    renderWithQuery(<FrameworksClient />);
    await waitFor(() => expect(screen.getByText("Matric Punjab — Physics")).toBeInTheDocument());
  });
});
