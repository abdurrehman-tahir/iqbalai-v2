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
  getUser: (...args: unknown[]) => mockGetUser(...args),
  clearToken: vi.fn(),
  getLogoutUrl: vi.fn(() => "http://localhost:9000/logout"),
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

describe("AdminShell — navigation", () => {
  beforeEach(() => { mockGetUser.mockReturnValue(null); });

  it("renders all sidebar nav links", () => {
    render(<AdminShell><div /></AdminShell>);
    const links = screen.getAllByRole("link");
    const hrefs = links.map((l) => l.getAttribute("href"));
    expect(hrefs).toContain("/admin/languages");
    expect(hrefs).toContain("/admin/personas");
    expect(hrefs).toContain("/admin/exam-syllabi");
    expect(hrefs).toContain("/admin/subscription-tiers");
    expect(hrefs).toContain("/admin/tos");
    expect(hrefs).toContain("/admin/library");
    expect(hrefs).toContain("/admin/audit-log");
  });

  it("renders children in the main content area", () => {
    render(<AdminShell><p>hello world</p></AdminShell>);
    expect(screen.getByText("hello world")).toBeInTheDocument();
  });
});
