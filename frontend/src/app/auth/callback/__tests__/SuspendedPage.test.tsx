import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { SuspendedPage } from "../SuspendedPage";

vi.mock("next-intl", () => import("@/test/mocks/next-intl"));

describe("SuspendedPage (T-232)", () => {
  it("renders suspended messaging", () => {
    render(<SuspendedPage />);
    expect(screen.getByRole("heading", { name: "title" })).toBeInTheDocument();
    expect(screen.getByText("description")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "back_to_login" })).toHaveAttribute("href", "/login");
  });
});
