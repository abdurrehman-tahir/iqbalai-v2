import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { AdminPageHeader } from "../AdminPageHeader";

describe("AdminPageHeader (T-231)", () => {
  it("renders title and optional subtitle", () => {
    render(<AdminPageHeader title="Languages" subtitle="Deployment config" />);
    expect(screen.getByRole("heading", { level: 1, name: "Languages" })).toBeInTheDocument();
    expect(screen.getByText("Deployment config")).toBeInTheDocument();
  });
});
