/** T-188 — My Highlights is reachable from the student shell nav (Rule 13). */
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import enMessages from "../../../../messages/en/common.json";
import { STUDENT_NAV, StudentShell } from "../StudentShell";

let pathname = "/student/highlights";

vi.mock("next/navigation", () => ({ usePathname: () => pathname }));
vi.mock("@/hooks/use-current-user", () => ({
  useCurrentUser: () => ({ user: { email: "student@example.com" } }),
}));
vi.mock("@/lib/auth", () => ({ performLogout: vi.fn() }));
vi.mock("../ModeSwitcher", () => ({ ModeSwitcher: () => null }));
vi.mock("../StudentOnboardingGate", () => ({
  StudentOnboardingGate: ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  ),
}));

function renderShell() {
  return render(
    <NextIntlClientProvider locale="en" messages={enMessages}>
      <StudentShell>
        <p>content</p>
      </StudentShell>
    </NextIntlClientProvider>,
  );
}

describe("StudentShell nav", () => {
  it("links every nav entry and marks the current page", () => {
    pathname = "/student/highlights";
    renderShell();
    const nav = screen.getByRole("navigation", { name: "Student navigation" });
    expect(nav).toBeInTheDocument();
    // Derived from the nav config itself — never a hand-kept list (Rule 14).
    for (const entry of STUDENT_NAV) {
      const key = entry.labelKey.replace(
        "nav.",
        "",
      ) as keyof typeof enMessages.student.nav;
      const label = enMessages.student.nav[key];
      expect(screen.getByRole("link", { name: label })).toHaveAttribute(
        "href",
        entry.href,
      );
    }
    expect(screen.getByRole("link", { name: "My Highlights" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByRole("link", { name: "Home" })).not.toHaveAttribute(
      "aria-current",
    );
  });

  it("hides the nav during onboarding", () => {
    pathname = "/student/onboarding";
    renderShell();
    expect(screen.queryByTestId("student-nav")).not.toBeInTheDocument();
  });
});
