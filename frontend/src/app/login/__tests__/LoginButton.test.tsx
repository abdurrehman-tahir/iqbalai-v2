import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LoginButton } from "../LoginButton";

// T-245: login navigates to the API's own /auth/login (server-owned redirect,
// ARCH §6.4), never builds an Authentik authorize URL in the browser.
vi.mock("@/lib/auth", () => ({
  getLoginRedirectUrl: vi.fn(() => "http://localhost:8000/api/v1/auth/login"),
}));

beforeEach(() => {
  vi.clearAllMocks();
  Object.defineProperty(window, "location", {
    value: { href: "" },
    writable: true,
  });
});

describe("LoginButton (T-245)", () => {
  it("navigates to the API-owned login redirect on click", async () => {
    const user = userEvent.setup();
    render(<LoginButton label="Sign in" />);
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    expect(window.location.href).toBe("http://localhost:8000/api/v1/auth/login");
  });
});
