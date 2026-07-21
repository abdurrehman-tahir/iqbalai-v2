import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
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

vi.mock("@/lib/auth", () => ({
  getLogoutUrl: vi.fn(() => "http://localhost:9000/logout"),
}));

// T-245: AdminShell reads "who am I" via useCurrentUser() (GET /auth/me),
// not sessionStorage — mock the hook directly rather than wiring a
// QueryClientProvider + API mock through every test.
const mockUseCurrentUser = vi.fn();
vi.mock("@/hooks/use-current-user", () => ({
  useCurrentUser: () => mockUseCurrentUser(),
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
});

describe("AdminShell — user display", () => {
  it("renders the fallback 'Platform Admin' before user loads (SSR-safe initial state)", () => {
    mockUseCurrentUser.mockReturnValue({ user: null, isLoading: true });
    render(<AdminShell><div>page</div></AdminShell>);
    // Initial render with null user → shows fallback text
    expect(screen.getByText("admin_role")).toBeInTheDocument();
  });

  it("shows the user email after useCurrentUser resolves", () => {
    mockUseCurrentUser.mockReturnValue({
      user: {
        user_id: "u1",
        email: "admin@iqbalai.com",
        role: "platform_admin",
        tenant_type: "school",
      },
      isLoading: false,
    });
    render(<AdminShell><div>page</div></AdminShell>);
    expect(screen.getByText("admin@iqbalai.com")).toBeInTheDocument();
  });
});

function makeUser(role: string) {
  return {
    user_id: "u1",
    email: "admin@iqbalai.com",
    role,
    tenant_type: "school",
  };
}

describe("AdminShell — role-aware navigation (T-227)", () => {
  it("renders the platform_admin's nav items", () => {
    mockUseCurrentUser.mockReturnValue({ user: makeUser("platform_admin"), isLoading: false });
    render(<AdminShell><div /></AdminShell>);
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

  it("hides admin items from a role above which they sit (teacher sees none)", () => {
    mockUseCurrentUser.mockReturnValue({ user: makeUser("teacher"), isLoading: false });
    render(<AdminShell><div /></AdminShell>);
    expect(screen.queryByRole("link", { name: /languages/i })).toBeNull();
    expect(screen.queryAllByRole("link")).toHaveLength(0);
  });

  it("renders no nav items before the user resolves (null user → empty)", () => {
    mockUseCurrentUser.mockReturnValue({ user: null, isLoading: true });
    render(<AdminShell><div /></AdminShell>);
    expect(screen.queryAllByRole("link")).toHaveLength(0);
  });

  it("renders children in the main content area", () => {
    mockUseCurrentUser.mockReturnValue({ user: null, isLoading: true });
    render(<AdminShell><p>hello world</p></AdminShell>);
    expect(screen.getByText("hello world")).toBeInTheDocument();
  });
});
