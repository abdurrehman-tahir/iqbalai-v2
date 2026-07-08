import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("next-intl", () => import("@/test/mocks/next-intl"));

const { forgotPassword } = vi.hoisted(() => ({
  forgotPassword: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  authApi: { forgotPassword },
}));

import { ForgotPasswordForm } from "../ForgotPasswordForm";

describe("ForgotPasswordForm (M-07b T-243)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    forgotPassword.mockResolvedValue(null);
  });

  it("shows success after submit without revealing whether the email exists", async () => {
    render(<ForgotPasswordForm />);
    await userEvent.type(screen.getByLabelText("email_label"), "ghost@iqbalai.dev");
    await userEvent.click(screen.getByRole("button", { name: "submit" }));

    await waitFor(() =>
      expect(screen.getByText("success_message")).toBeInTheDocument(),
    );
    expect(forgotPassword).toHaveBeenCalledWith("ghost@iqbalai.dev");
  });
});
