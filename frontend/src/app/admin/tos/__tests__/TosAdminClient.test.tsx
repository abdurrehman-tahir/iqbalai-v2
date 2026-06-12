import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TosAdminClient } from "../TosAdminClient";
import { renderWithQuery } from "@/test/helpers/render-admin";

vi.mock("next-intl", () => import("@/test/mocks/next-intl"));
vi.mock("@/hooks/use-client-auth", () => ({
  useClientAuth: () => ({ mounted: true, token: "tok" }),
}));

const mockList = vi.fn();
const mockListDisclaimer = vi.fn();
vi.mock("@/lib/api", () => ({
  tosApi: {
    list: (...a: unknown[]) => mockList(...a),
    listDisclaimer: (...a: unknown[]) => mockListDisclaimer(...a),
    publish: vi.fn(),
    publishDisclaimer: vi.fn(),
  },
}));

beforeEach(() => vi.clearAllMocks());

describe("TosAdminClient — four UI states (T-232/T-235)", () => {
  it("loading shows heading", () => {
    mockList.mockReturnValue(new Promise(() => {}));
    renderWithQuery(<TosAdminClient type="tos" />);
    expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
  });

  it("error state", async () => {
    mockList.mockRejectedValue(new Error("x"));
    renderWithQuery(<TosAdminClient type="tos" />);
    await waitFor(() => expect(screen.getByText("error")).toBeInTheDocument());
  });

  it("empty state with publish action", async () => {
    mockList.mockResolvedValue([]);
    renderWithQuery(<TosAdminClient type="tos" />);
    await waitFor(() => expect(screen.getByText("empty.title")).toBeInTheDocument());
  });

  it("success lists versions", async () => {
    mockList.mockResolvedValue([
      { id: "t1", version: 1, content: "# Terms", effective_at: "2026-01-01T00:00:00Z" },
    ]);
    renderWithQuery(<TosAdminClient type="tos" />);
    await waitFor(() => expect(screen.getByText("# Terms")).toBeInTheDocument());
  });

  it("opens publish modal", async () => {
    mockList.mockResolvedValue([
      { id: "t1", version: 1, content: "# Terms", effective_at: "2026-01-01T00:00:00Z" },
    ]);
    const user = userEvent.setup();
    renderWithQuery(<TosAdminClient type="tos" />);
    await waitFor(() => expect(screen.getByText("# Terms")).toBeInTheDocument());
    await user.click(screen.getAllByText("publish_button")[0]);
    expect(screen.getByText("modal.title")).toBeInTheDocument();
  });

  it("disclaimer type uses listDisclaimer", async () => {
    mockListDisclaimer.mockResolvedValue([
      { id: "d1", version: 1, content: "AI disclaimer", effective_at: "2026-01-01T00:00:00Z" },
    ]);
    renderWithQuery(<TosAdminClient type="disclaimer" />);
    await waitFor(() => expect(mockListDisclaimer).toHaveBeenCalled());
    await waitFor(() => expect(screen.getByText("AI disclaimer")).toBeInTheDocument());
  });
});
