import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("next-intl", () => import("@/test/mocks/next-intl"));

// Hoisted so the (hoisted) vi.mock factories below can reference them safely.
const { mockReplace, login, getCurrent, ApiError } = vi.hoisted(() => {
  class ApiError extends Error {
    status: number;
    code: string;
    constructor(status: number, code: string, message: string) {
      super(message);
      this.status = status;
      this.code = code;
    }
  }
  return { mockReplace: vi.fn(), login: vi.fn(), getCurrent: vi.fn(), ApiError };
});

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mockReplace }),
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/lib/api", () => ({
  ApiError,
  authApi: { login },
  tosApi: { getCurrent },
}));

import { LoginForm } from "../LoginForm";

const OK_USER = {
  user_id: "u-1",
  email: "teacher@iqbalai.dev",
  role: "teacher",
  district_id: null,
  school_id: null,
  tos_acceptance_required: false,
  current_tos_version_id: null,
  account_status: "active",
};

async function fillAndSubmit() {
  await userEvent.type(screen.getByLabelText("email_label"), "teacher@iqbalai.dev");
  await userEvent.type(screen.getByLabelText("password_label"), "devpassword");
  await userEvent.click(screen.getByRole("button", { name: "submit" }));
}

describe("LoginForm (M-07b T-241)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
  });

  it("renders email + password fields and a submit button", () => {
    render(<LoginForm />);
    expect(screen.getByLabelText("email_label")).toBeInTheDocument();
    expect(screen.getByLabelText("password_label")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "submit" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "forgot_password" })).toHaveAttribute(
      "href",
      "/login/forgot-password",
    );
    expect(screen.getByRole("link", { name: "create_account" })).toHaveAttribute(
      "href",
      "/signup",
    );
  });

  it("posts credentials and redirects to the role dashboard on success", async () => {
    login.mockResolvedValue(OK_USER);
    render(<LoginForm />);
    await fillAndSubmit();

    await waitFor(() => expect(login).toHaveBeenCalledWith({
      email: "teacher@iqbalai.dev",
      password: "devpassword",
    }));
    await waitFor(() => expect(mockReplace).toHaveBeenCalledWith("/teacher"));
  });

  it("shows an inline error and does not redirect on invalid credentials", async () => {
    login.mockRejectedValue(new ApiError(401, "INVALID_CREDENTIALS", "bad"));
    render(<LoginForm />);
    await fillAndSubmit();

    await waitFor(() =>
      expect(screen.getByText("error.invalid_credentials")).toBeInTheDocument(),
    );
    expect(mockReplace).not.toHaveBeenCalled();
  });

  it("shows the ToS modal on first login instead of redirecting", async () => {
    login.mockResolvedValue({
      ...OK_USER,
      tos_acceptance_required: true,
      current_tos_version_id: "v1",
    });
    getCurrent.mockResolvedValue({ id: "v1", version: 1, content: "Please accept these terms." });
    render(<LoginForm />);
    await fillAndSubmit();

    await waitFor(() =>
      expect(screen.getByText("Please accept these terms.")).toBeInTheDocument(),
    );
    expect(mockReplace).not.toHaveBeenCalled();
  });
});
