import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { EmptyState } from "../empty-state";

vi.mock("next/link", () => ({
  default: ({ href, children }: { href: string; children: React.ReactNode }) => (
    <a href={href}>{children}</a>
  ),
}));

describe("EmptyState (T-235)", () => {
  it("renders title and description", () => {
    render(<EmptyState title="Nothing here" description="Add something" />);
    expect(screen.getByText("Nothing here")).toBeInTheDocument();
    expect(screen.getByText("Add something")).toBeInTheDocument();
  });

  it("renders href action", () => {
    render(
      <EmptyState
        title="Empty"
        description="Desc"
        action={{ label: "Create", href: "/new" }}
      />,
    );
    expect(screen.getByRole("link", { name: "Create" })).toHaveAttribute("href", "/new");
  });
});
