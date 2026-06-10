import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { LibraryClient } from "../LibraryClient";
import { renderWithQuery } from "@/test/helpers/render-admin";

vi.mock("next-intl", () => import("@/test/mocks/next-intl"));
vi.mock("@/hooks/use-client-auth", () => ({
  useClientAuth: () => ({ mounted: true, token: "tok" }),
}));

const mockList = vi.fn();
vi.mock("@/lib/api", () => ({
  libraryApi: {
    list: (...a: unknown[]) => mockList(...a),
    softDelete: vi.fn(),
  },
}));

beforeEach(() => vi.clearAllMocks());

describe("LibraryClient — four UI states (T-235)", () => {
  it("loading shows heading", () => {
    mockList.mockReturnValue(new Promise(() => {}));
    renderWithQuery(<LibraryClient />);
    expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
  });

  it("error state", async () => {
    mockList.mockRejectedValue(new Error("x"));
    renderWithQuery(<LibraryClient />);
    await waitFor(() => expect(screen.getByText("error")).toBeInTheDocument());
  });

  it("empty state", async () => {
    mockList.mockResolvedValue([]);
    renderWithQuery(<LibraryClient />);
    await waitFor(() => expect(screen.getByText("empty.title")).toBeInTheDocument());
  });

  it("success lists books", async () => {
    mockList.mockResolvedValue([
      {
        id: "b1",
        title: "math-guide.pdf",
        status: "available",
        language: "en",
        content_type: "curriculum",
        created_at: "2026-06-01T00:00:00Z",
      },
    ]);
    renderWithQuery(<LibraryClient />);
    await waitFor(() => expect(screen.getByText("math-guide.pdf")).toBeInTheDocument());
  });
});
