import { render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { IndependentLectureRedirect } from "../IndependentLectureRedirect";
import en from "../../../../messages/en/common.json";

const replace = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
}));

vi.mock("@/hooks/use-current-user", () => ({
  useCurrentUser: vi.fn(),
}));

import { useCurrentUser } from "@/hooks/use-current-user";

function renderGuard() {
  return render(
    <NextIntlClientProvider locale="en" messages={en}>
      <IndependentLectureRedirect>
        <div data-testid="lecture-shell">Lecture shell</div>
      </IndependentLectureRedirect>
    </NextIntlClientProvider>,
  );
}

describe("IndependentLectureRedirect (T-209)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders children for school students", () => {
    vi.mocked(useCurrentUser).mockReturnValue({
      user: { role: "student", email: "s@x.com", user_id: "1" } as never,
      isLoading: false,
    });
    renderGuard();
    expect(screen.getByTestId("lecture-shell")).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });

  it("redirects independent students to self-study home", () => {
    vi.mocked(useCurrentUser).mockReturnValue({
      user: {
        role: "independent_student",
        email: "i@x.com",
        user_id: "2",
      } as never,
      isLoading: false,
    });
    renderGuard();
    expect(screen.getByTestId("independent-lecture-redirect")).toBeInTheDocument();
    expect(screen.queryByTestId("lecture-shell")).not.toBeInTheDocument();
    expect(replace).toHaveBeenCalledWith("/independent/student");
  });
});
