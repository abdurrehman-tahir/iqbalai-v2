import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("next-intl", () => import("@/test/mocks/next-intl"));

import { SocialButtons } from "../SocialButtons";

describe("SocialButtons", () => {
  it("renders one button per provider", () => {
    render(<SocialButtons />);
    expect(screen.getByRole("button", { name: /google/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /linkedin/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /github/i })).toBeInTheDocument();
  });

  it("keeps every provider disabled while federated sign-in is not wired up", () => {
    render(<SocialButtons />);
    for (const button of screen.getAllByRole("button")) {
      expect(button).toBeDisabled();
    }
  });
});
