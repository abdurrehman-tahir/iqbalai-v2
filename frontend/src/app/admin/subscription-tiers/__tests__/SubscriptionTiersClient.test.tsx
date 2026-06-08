import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { SubscriptionTiersClient } from "../SubscriptionTiersClient";
import { renderWithQuery } from "@/test/helpers/render-admin";

vi.mock("next-intl", () => import("@/test/mocks/next-intl"));
vi.mock("@/hooks/use-client-auth", () => ({
  useClientAuth: () => ({ mounted: true, token: "tok" }),
}));

const mockList = vi.fn();
vi.mock("@/lib/api", () => ({
  subscriptionsApi: {
    list: (...a: unknown[]) => mockList(...a),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
  },
}));

beforeEach(() => vi.clearAllMocks());

describe("SubscriptionTiersClient — four UI states (T-235)", () => {
  it("loading shows heading", () => {
    mockList.mockReturnValue(new Promise(() => {}));
    renderWithQuery(<SubscriptionTiersClient />);
    expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
  });

  it("error state", async () => {
    mockList.mockRejectedValue(new Error("x"));
    renderWithQuery(<SubscriptionTiersClient />);
    await waitFor(() => expect(screen.getByText("error")).toBeInTheDocument());
  });

  it("empty state", async () => {
    mockList.mockResolvedValue([]);
    renderWithQuery(<SubscriptionTiersClient />);
    await waitFor(() => expect(screen.getByText("empty.title")).toBeInTheDocument());
  });

  it("success lists tiers", async () => {
    mockList.mockResolvedValue([
      {
        id: "tier-1",
        name: "School Basic",
        pricing_monthly_pkr: 5000,
        caps: {},
        applies_to_role: "school_admin",
        is_active: true,
      },
    ]);
    renderWithQuery(<SubscriptionTiersClient />);
    await waitFor(() => expect(screen.getByText("School Basic")).toBeInTheDocument());
  });
});
