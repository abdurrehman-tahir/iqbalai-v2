import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useCurrentUser } from "../use-current-user";

const meMock = vi.fn();
vi.mock("@/lib/api", () => ({
  authApi: { me: (...args: unknown[]) => meMock(...args) },
}));

const mockClientAuth = vi.fn();
vi.mock("@/hooks/use-client-auth", () => ({
  useClientAuth: () => mockClientAuth(),
}));

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("useCurrentUser (T-245)", () => {
  it("does not fetch before the client has mounted (SSR-safety gate)", () => {
    mockClientAuth.mockReturnValue({ mounted: false, token: null });
    renderHook(() => useCurrentUser(), { wrapper });
    expect(meMock).not.toHaveBeenCalled();
  });

  it("fetches GET /auth/me once mounted, returns the resolved user", async () => {
    mockClientAuth.mockReturnValue({ mounted: true, token: "cookie-session" });
    meMock.mockResolvedValue({ user_id: "u1", email: "t@school.pk", role: "teacher" });

    const { result } = renderHook(() => useCurrentUser(), { wrapper });
    expect(result.current.user).toBeNull();

    await waitFor(() => expect(result.current.user?.email).toBe("t@school.pk"));
    expect(meMock).toHaveBeenCalledOnce();
  });

  it("returns null (not throw) while unauthenticated/unmounted", () => {
    mockClientAuth.mockReturnValue({ mounted: false, token: null });
    const { result } = renderHook(() => useCurrentUser(), { wrapper });
    expect(result.current.user).toBeNull();
  });
});
