import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NotificationBell } from "../NotificationBell";

// ── Mocks ─────────────────────────────────────────────────────────────────────

vi.mock("next-intl", () => import("@/test/mocks/next-intl"));

const mockList = vi.fn();
const mockMarkRead = vi.fn();

vi.mock("@/lib/api", () => ({
  notificationsApi: {
    list: (...args: unknown[]) => mockList(...args),
    markRead: (...args: unknown[]) => mockMarkRead(...args),
  },
}));

// ── Helpers ───────────────────────────────────────────────────────────────────

function makeNotification(overrides: Partial<{
  id: string; is_read: boolean; title: string; body: string; feature_namespace: string;
}> = {}) {
  return {
    id: "n1",
    feature_namespace: "tos",
    title: "New ToS",
    body: "Please accept the updated terms.",
    is_read: false,
    created_at: "2026-06-01T00:00:00Z",
    ...overrides,
  };
}

function renderBell() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <NotificationBell />
    </QueryClientProvider>,
  );
}

// ── Tests ─────────────────────────────────────────────────────────────────────

beforeEach(() => {
  vi.clearAllMocks();
  mockMarkRead.mockResolvedValue(undefined);
});

describe("NotificationBell — idle / no data", () => {
  it("renders the bell button", async () => {
    mockList.mockResolvedValue([]);
    renderBell();
    expect(screen.getByRole("button", { name: "aria_label" })).toBeInTheDocument();
  });

  it("shows no badge when there are no unread notifications", async () => {
    mockList.mockResolvedValue([makeNotification({ is_read: true })]);
    renderBell();
    await waitFor(() => expect(mockList).toHaveBeenCalledOnce());
    // The count badge (aria-hidden span) should not exist
    const badge = screen.queryByText(/^\d+\+?$/);
    expect(badge).toBeNull();
  });
});

describe("NotificationBell — unread count badge", () => {
  it("shows the unread count badge", async () => {
    mockList.mockResolvedValue([
      makeNotification({ id: "n1", is_read: false }),
      makeNotification({ id: "n2", is_read: false }),
      makeNotification({ id: "n3", is_read: true }),
    ]);
    renderBell();
    await waitFor(() => expect(screen.getByText("2")).toBeInTheDocument());
  });

  it("caps badge at 99+", async () => {
    const many = Array.from({ length: 100 }, (_, i) =>
      makeNotification({ id: `n${i}`, is_read: false }),
    );
    mockList.mockResolvedValue(many);
    renderBell();
    await waitFor(() => expect(screen.getByText("99+")).toBeInTheDocument());
  });
});

describe("NotificationBell — panel open/close", () => {
  it("opens the notification panel on click", async () => {
    mockList.mockResolvedValue([makeNotification()]);
    renderBell();
    await userEvent.click(screen.getByRole("button", { name: "aria_label" }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("shows empty state when no notifications", async () => {
    mockList.mockResolvedValue([]);
    renderBell();
    await userEvent.click(screen.getByRole("button", { name: "aria_label" }));
    await waitFor(() =>
      expect(screen.getByText("empty")).toBeInTheDocument(),
    );
  });

  it("lists notification titles in the panel", async () => {
    mockList.mockResolvedValue([
      makeNotification({ id: "n1", title: "ToS Updated" }),
      makeNotification({ id: "n2", title: "System Maintenance", is_read: true }),
    ]);
    renderBell();
    await userEvent.click(screen.getByRole("button", { name: "aria_label" }));
    await waitFor(() => {
      expect(screen.getByText("ToS Updated")).toBeInTheDocument();
      expect(screen.getByText("System Maintenance")).toBeInTheDocument();
    });
  });
});

describe("NotificationBell — mark as read", () => {
  it("calls markRead when a notification is clicked", async () => {
    mockList.mockResolvedValue([makeNotification({ id: "n1", title: "ToS Updated" })]);
    renderBell();
    await userEvent.click(screen.getByRole("button", { name: "aria_label" }));
    await waitFor(() => screen.getByText("ToS Updated"));
    await userEvent.click(screen.getByText("ToS Updated"));
    // T-245: `token` is now a non-secret sentinel (the cookie carries real
    // auth) — assert the notification id, not the inert placeholder string.
    expect(mockMarkRead).toHaveBeenCalledWith(expect.any(String), "n1");
  });
});
