import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("next-intl", () => import("@/test/mocks/next-intl"));

vi.mock("@/components/LanguageSwitcher", () => ({
  default: () => null,
}));

import { SignupHub } from "../SignupHub";

describe("SignupHub (M-07b T-242)", () => {
  it("renders all four signup paths", () => {
    render(<SignupHub />);
    expect(screen.getByText("cards.invite.title")).toBeInTheDocument();
    expect(screen.getByText("cards.independent.title")).toBeInTheDocument();
    expect(screen.getByText("cards.parent.title")).toBeInTheDocument();
    expect(screen.getByText("cards.school.title")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /cards.invite.cta/i })).toHaveAttribute(
      "href",
      "/accept-invite",
    );
    expect(screen.getByRole("link", { name: /cards.independent.cta/i })).toHaveAttribute(
      "href",
      "/independent/signup",
    );
    expect(screen.getByRole("link", { name: /cards.parent.cta/i })).toHaveAttribute(
      "href",
      "/parent/signup",
    );
  });
});
