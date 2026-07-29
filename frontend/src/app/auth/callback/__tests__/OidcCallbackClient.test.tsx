import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { OidcCallbackClient } from "../OidcCallbackClient";

vi.mock("next-intl", () => import("@/test/mocks/next-intl"));

const replaceMock = vi.fn();
let searchParamsValue = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: replaceMock }),
  useSearchParams: () => searchParamsValue,
}));

vi.mock("@/hooks/use-client-auth", () => ({
  useClientAuth: () => ({ mounted: true, token: "cookie-session" }),
}));

const meMock = vi.fn();
const getCurrentMock = vi.fn();
const acceptTosMock = vi.fn();
const declineTosMock = vi.fn();

vi.mock("@/lib/api", () => {
  class MockApiError extends Error {
    constructor(
      public status: number,
      public code: string,
      message: string,
    ) {
      super(message);
    }
  }
  return {
    authApi: { me: (...args: unknown[]) => meMock(...args) },
    tosApi: {
      getCurrent: (...args: unknown[]) => getCurrentMock(...args),
      acceptTos: (...args: unknown[]) => acceptTosMock(...args),
      declineTos: (...args: unknown[]) => declineTosMock(...args),
    },
    ApiError: MockApiError,
  };
});

const TOS = { id: "tos-1", version: 3, content: "Terms and conditions." };

beforeEach(() => {
  vi.clearAllMocks();
  searchParamsValue = new URLSearchParams();
  meMock.mockResolvedValue({ user_id: "u1", email: "t@school.pk", role: "teacher" });
  getCurrentMock.mockResolvedValue(TOS);
});

describe("OidcCallbackClient (T-245)", () => {
  it("redirects to /login when landed on without ?tos_required=1 (never handles a code)", async () => {
    render(<OidcCallbackClient />);
    await waitFor(() => expect(replaceMock).toHaveBeenCalledWith("/login"));
    expect(meMock).not.toHaveBeenCalled();
  });

  it("loads and shows the ToS modal when tos_required=1", async () => {
    searchParamsValue = new URLSearchParams({ tos_required: "1" });
    render(<OidcCallbackClient />);
    await waitFor(() => expect(screen.getByText("Terms and conditions.")).toBeInTheDocument());
    expect(meMock).toHaveBeenCalledOnce();
    expect(getCurrentMock).toHaveBeenCalledOnce();
  });

  it("accepting redirects to the fetched role's dashboard", async () => {
    searchParamsValue = new URLSearchParams({ tos_required: "1" });
    acceptTosMock.mockResolvedValue({ accepted: true });
    const user = userEvent.setup();
    render(<OidcCallbackClient />);
    await waitFor(() => expect(screen.getByRole("button", { name: "accept" })).not.toBeDisabled());
    await user.click(screen.getByRole("button", { name: "accept" }));
    await waitFor(() => expect(replaceMock).toHaveBeenCalledWith("/teacher"));
    expect(acceptTosMock).toHaveBeenCalledWith("cookie-session", "tos-1");
  });

  it("declining shows the suspended state", async () => {
    searchParamsValue = new URLSearchParams({ tos_required: "1" });
    declineTosMock.mockResolvedValue({ declined: true });
    const user = userEvent.setup();
    render(<OidcCallbackClient />);
    await waitFor(() => screen.getByRole("button", { name: "decline" }));
    await user.click(screen.getByRole("button", { name: "decline" }));
    await waitFor(() => expect(screen.getByText("suspended.title")).toBeInTheDocument());
  });

  it("shows an error state when the ToS fetch fails", async () => {
    searchParamsValue = new URLSearchParams({ tos_required: "1" });
    getCurrentMock.mockRejectedValue(new Error("network down"));
    render(<OidcCallbackClient />);
    await waitFor(() => expect(screen.getByText("error.generic")).toBeInTheDocument());
  });
});
