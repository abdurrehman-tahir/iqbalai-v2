import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NextIntlClientProvider } from "next-intl";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { ParentHomeClient } from "../ParentHomeClient";
import en from "../../../../messages/en/common.json";

const getConnectionsMock = vi.fn().mockResolvedValue({
  parent_state: "PARENT_ACTIVE_UNLINKED",
  links: [],
});

const createLinkMock = vi.fn().mockResolvedValue({
  id: "link-1",
  status: "pending",
  student_email: "student@example.com",
});

vi.mock("@/hooks/use-client-auth", () => ({
  useClientAuth: () => ({ mounted: true, token: "tok" }),
}));

vi.mock("@/lib/api", () => ({
  parentChildLinksApi: {
    getConnections: (...args: unknown[]) => getConnectionsMock(...args),
    createLinkRequest: (...args: unknown[]) => createLinkMock(...args),
  },
}));

function renderHome() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <NextIntlClientProvider locale="en" messages={en}>
        <ParentHomeClient />
      </NextIntlClientProvider>
    </QueryClientProvider>,
  );
}

describe("ParentHomeClient (T-081)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders link request form", async () => {
    renderHome();
    expect(await screen.findByRole("heading", { name: /Link to your child/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/Student email/i)).toBeInTheDocument();
  });

  it("submits link request", async () => {
    const user = userEvent.setup();
    renderHome();
    await screen.findByRole("heading", { name: /Link to your child/i });
    await user.type(screen.getByLabelText(/Student email/i), "student@example.com");
    await user.click(screen.getByRole("button", { name: /Send link request/i }));
    await waitFor(() => {
      expect(createLinkMock).toHaveBeenCalledWith("tok", "student@example.com");
    });
  });
});
