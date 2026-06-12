import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { SyllabiClient } from "../SyllabiClient";
import { renderWithQuery } from "@/test/helpers/render-admin";

vi.mock("next-intl", () => import("@/test/mocks/next-intl"));
vi.mock("@/hooks/use-client-auth", () => ({
  useClientAuth: () => ({ mounted: true, token: "tok" }),
}));

const mockList = vi.fn();
vi.mock("@/lib/api", () => ({
  syllabiApi: {
    list: (...a: unknown[]) => mockList(...a),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
  },
}));

beforeEach(() => vi.clearAllMocks());

describe("SyllabiClient — four UI states (T-235)", () => {
  it("loading shows heading", () => {
    mockList.mockReturnValue(new Promise(() => {}));
    renderWithQuery(<SyllabiClient />);
    expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
  });

  it("error shows heading + retry", async () => {
    mockList.mockRejectedValue(new Error("x"));
    renderWithQuery(<SyllabiClient />);
    await waitFor(() => expect(screen.getByText("error")).toBeInTheDocument());
  });

  it("empty shows empty state", async () => {
    mockList.mockResolvedValue([]);
    renderWithQuery(<SyllabiClient />);
    await waitFor(() => expect(screen.getByText("empty.title")).toBeInTheDocument());
  });

  it("success lists syllabi", async () => {
    mockList.mockResolvedValue([
      {
        id: "s1",
        name: "FBISE Matric",
        exam_board: "FBISE",
        region: null,
        grade_range_min: null,
        grade_range_max: null,
        language: "en",
        version_number: 1,
        is_active: true,
        created_at: "2026-01-01T00:00:00Z",
      },
    ]);
    renderWithQuery(<SyllabiClient />);
    await waitFor(() => expect(screen.getByText("FBISE Matric")).toBeInTheDocument());
  });
});
