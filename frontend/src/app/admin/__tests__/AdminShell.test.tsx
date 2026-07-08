import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import { AdminShell } from "../AdminShell";

// ── Mocks ─────────────────────────────────────────────────────────────────────

vi.mock("next-intl", () => import("@/test/mocks/next-intl"));
vi.mock("next/navigation", () => ({
  usePathname: vi.fn(() => "/admin/languages"),
}));
vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }) => (
    <a href={href} {...props}>{children}</a>
  ),
}));

const mockGetUser = vi.fn();
vi.mock("@/lib/auth", () => ({
  performLogout: vi.fn(),
  getUser: (...args: unknown[]) => mockGetUser(...args),
}));

// NotificationBell fetches data — stub it out to keep tests focused on AdminShell
vi.mock("@/components/admin/NotificationBell", () => ({
  NotificationBell: () => <div data-testid="notification-bell" />,
}));

vi.mock("@/components/LanguageSwitcher", () => ({
  default: () => <div data-testid="language-switcher" />,
}));

// ── Tests ─────────────────────────────────────────────────────────────────────

beforeEach(() => {
  vi.clearAllMocks();
  sessionStorage.clear();
});

describe("AdminShell — user display", () => {
  it("renders the fallback 'Platform Admin' before user loads (SSR-safe initial state)", () => {
    mockGetUser.mockReturnValue(null);
    render(<AdminShell><div>page</div></AdminShell>);
    // Initial render with null user → shows fallback text
    expect(screen.getByText("admin_role")).toBeInTheDocument();
  });

  it("shows the user email after mount when getUser returns data", async () => {
    mockGetUser.mockReturnValue({
      user_id: "u1",
      email: "admin@iqbalai.com",
      role: "platform_admin",
      tos_acceptance_required: false,
      current_tos_version_id: null,
    });
    // Wrap in act so the useEffect that calls setUser runs
    await act(async () => {
      render(<AdminShell><div>page</div></AdminShell>);
    });
    expect(screen.getByText("admin@iqbalai.com")).toBeInTheDocument();
  });
});

function makeUser(role: string) {
  return {
    user_id: "u1",
    email: "admin@iqbalai.com",
    role,
    tos_acceptance_required: false,
    current_tos_version_id: null,
  };
}

describe("AdminShell — role-aware navigation (T-227)", () => {
  it("renders the platform_admin's nav items", async () => {
    mockGetUser.mockReturnValue(makeUser("platform_admin"));
    await act(async () => {
      render(<AdminShell><div /></AdminShell>);
    });
    const hrefs = screen.getAllByRole("link").map((l) => l.getAttribute("href"));
    // Desktop sidebar + mobile drawer each render the set → assert membership.
    for (const href of [
      "/admin/languages",
      "/admin/personas",
      "/admin/exam-syllabi",
      "/admin/subscription-tiers",
      "/admin/tos",
      "/admin/library",
      "/admin/audit-log",
    ]) {
      expect(hrefs).toContain(href);
    }
  });

  it("hides admin items from a role above which they sit (teacher sees none)", async () => {
    mockGetUser.mockReturnValue(makeUser("teacher"));
    await act(async () => {
      render(<AdminShell><div /></AdminShell>);
    });
    expect(screen.queryByRole("link", { name: /languages/i })).toBeNull();
    expect(screen.queryAllByRole("link")).toHaveLength(0);
  });

  it("renders no nav items before the user resolves (null user → empty)", () => {
    mockGetUser.mockReturnValue(null);
    render(<AdminShell><div /></AdminShell>);
    expect(screen.queryAllByRole("link")).toHaveLength(0);
  });

  it("renders children in the main content area", () => {
    mockGetUser.mockReturnValue(null);
    render(<AdminShell><p>hello world</p></AdminShell>);
    expect(screen.getByText("hello world")).toBeInTheDocument();
  });
});
