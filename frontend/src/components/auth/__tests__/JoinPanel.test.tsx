import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("next-intl", () => import("@/test/mocks/next-intl"));

import { JoinPanel } from "@/app/login/JoinPanel";

describe("JoinPanel", () => {
  it("shows the join heading and a create-account link into the signup hub", () => {
    render(<JoinPanel />);
    expect(screen.getByRole("heading", { name: "title" })).toBeInTheDocument();
    const cta = screen.getByRole("link", { name: "cta" });
    expect(cta).toHaveAttribute("href", "/signup");
  });
});
