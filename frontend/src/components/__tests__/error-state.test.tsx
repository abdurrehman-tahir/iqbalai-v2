import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ErrorState } from "../error-state";

describe("ErrorState (T-235)", () => {
  it("renders description and retry", async () => {
    const onRetry = vi.fn();
    const user = userEvent.setup();
    render(
      <ErrorState description="Failed to load" onRetry={onRetry} retryLabel="Try again" />,
    );
    expect(screen.getByText("Failed to load")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(onRetry).toHaveBeenCalledOnce();
  });
});
