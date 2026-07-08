import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("next-intl", () => import("@/test/mocks/next-intl"));

const { useSearchParams, resetPassword, ApiError } = vi.hoisted(() => {
  class ApiError extends Error {
    status: number;
    code: string;
    constructor(status: number, code: string, message: string) {
      super(message);
      this.status = status;
      this.code = code;
    }
  }
  return {
    useSearchParams: vi.fn(),
    resetPassword: vi.fn(),
    ApiError,
  };
});

vi.mock("next/navigation", () => ({
  useSearchParams: () => useSearchParams(),
}));

vi.mock("@/lib/api", () => ({
  ApiError,
  authApi: { resetPassword },
}));

import { ResetPasswordForm } from "../ResetPasswordForm";

describe("ResetPasswordForm (M-07b T-243)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    resetPassword.mockResolvedValue(null);
  });

  it("shows missing-token error when no token is in the URL", () => {
    useSearchParams.mockReturnValue(new URLSearchParams());
    render(<ResetPasswordForm />);
    expect(screen.getByText("missing_token")).toBeInTheDocument();
  });

  it("shows invalid-token error when the API rejects the token", async () => {
    useSearchParams.mockReturnValue(new URLSearchParams("token=bad"));
    resetPassword.mockRejectedValue(new ApiError(400, "INVALID_RESET_TOKEN", "bad"));
    render(<ResetPasswordForm />);

    await userEvent.type(screen.getByLabelText("password_label"), "newpassword1");
    await userEvent.type(screen.getByLabelText("confirm_password_label"), "newpassword1");
    await userEvent.click(screen.getByRole("button", { name: "submit" }));

    await waitFor(() =>
      expect(screen.getByText("error.invalid_token")).toBeInTheDocument(),
    );
  });
});
