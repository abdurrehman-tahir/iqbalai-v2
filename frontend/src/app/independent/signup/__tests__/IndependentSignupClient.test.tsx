import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NextIntlClientProvider } from "next-intl";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { IndependentSignupClient } from "../IndependentSignupClient";
import en from "../../../../../messages/en/common.json";

const signupMock = vi.fn().mockResolvedValue({
  user_id: "user-1",
  email: "test@example.com",
  role: "independent_teacher",
  tenant_type: "independent",
  message: "ok",
});

vi.mock("@/lib/api", () => ({
  independentSignupApi: {
    getInfo: vi.fn().mockResolvedValue({
      roles: ["independent_teacher", "independent_student"],
      languages: ["en", "ur"],
    }),
    signup: (...args: unknown[]) => signupMock(...args),
  },
}));

vi.mock("@/lib/auth", () => ({
  clearToken: vi.fn(),
  getLoginUrl: vi.fn(() => "/login"),
}));

function renderSignup() {
  return render(
    <NextIntlClientProvider locale="en" messages={en}>
      <IndependentSignupClient />
    </NextIntlClientProvider>,
  );
}

describe("IndependentSignupClient (T-069)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders signup form with role selection", async () => {
    renderSignup();
    expect(await screen.findByRole("heading", { name: /Create your independent account/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/Full name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Email/i)).toBeInTheDocument();
  });

  it("submits signup and shows success", async () => {
    const user = userEvent.setup();
    renderSignup();

    await screen.findByRole("heading", { name: /Create your independent account/i });
    await user.type(screen.getByLabelText(/Full name/i), "Test User");
    await user.type(screen.getByLabelText(/Email/i), "test@example.com");
    await user.type(document.getElementById("password")!, "password123");
    await user.type(document.getElementById("confirm-password")!, "password123");
    await user.click(screen.getByRole("button", { name: /Create account/i }));

    await waitFor(() => {
      expect(signupMock).toHaveBeenCalled();
    });
    expect(await screen.findByText(/Your account is ready/i)).toBeInTheDocument();
  });
});
