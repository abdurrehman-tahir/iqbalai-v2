import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NextIntlClientProvider } from "next-intl";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { ParentSignupClient } from "../ParentSignupClient";
import en from "../../../../../messages/en/common.json";

const signupMock = vi.fn().mockResolvedValue({
  user_id: "user-1",
  email: "parent@example.com",
  role: "parent",
  tenant_type: "school",
  parent_state: "PARENT_REGISTERED",
  message: "ok",
});

vi.mock("@/lib/api", () => ({
  parentSignupApi: {
    getInfo: vi.fn().mockResolvedValue({
      languages: ["en", "ur"],
    }),
    signup: (...args: unknown[]) => signupMock(...args),
  },
}));

vi.mock("@/lib/auth", () => ({
  clearSession: vi.fn(),
  buildAppLoginUrl: vi.fn((email?: string) =>
    email ? `/login?email=${encodeURIComponent(email)}` : "/login",
  ),
}));

function renderSignup() {
  return render(
    <NextIntlClientProvider locale="en" messages={en}>
      <ParentSignupClient />
    </NextIntlClientProvider>,
  );
}

describe("ParentSignupClient (T-080)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders signup form", async () => {
    renderSignup();
    expect(await screen.findByRole("heading", { name: /Create your parent account/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/Full name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Email/i)).toBeInTheDocument();
  });

  it("submits signup and shows success", async () => {
    const user = userEvent.setup();
    renderSignup();

    await screen.findByRole("heading", { name: /Create your parent account/i });
    await user.type(screen.getByLabelText(/Full name/i), "Parent User");
    await user.type(screen.getByLabelText(/Email/i), "parent@example.com");
    await user.type(document.getElementById("password")!, "password123");
    await user.type(document.getElementById("confirm-password")!, "password123");
    await user.click(screen.getByRole("button", { name: /Create account/i }));

    await waitFor(() => {
      expect(signupMock).toHaveBeenCalled();
    });
    expect(await screen.findByText(/Verify your email and sign in/i)).toBeInTheDocument();
  });
});
