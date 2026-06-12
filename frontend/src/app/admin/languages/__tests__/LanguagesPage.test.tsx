import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import LanguagesPage from "../page";

vi.mock("next-intl", () => import("@/test/mocks/next-intl"));

describe("LanguagesPage (T-231/T-235)", () => {
  it("renders the page heading and four language cards", () => {
    render(<LanguagesPage />);
    expect(screen.getByRole("heading", { level: 1, name: "title" })).toBeInTheDocument();
    for (const code of ["en", "ur", "sd", "ps"]) {
      expect(document.querySelector(`[lang="${code}"]`)).toBeInTheDocument();
    }
  });
});
