import { render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import HomePage from "../page";
import en from "../../../messages/en/common.json";

function renderLanding() {
  return render(
    <NextIntlClientProvider locale="en" messages={en}>
      <HomePage />
    </NextIntlClientProvider>,
  );
}

describe("landing page", () => {
  it("renders the hero content", () => {
    renderLanding();
    expect(
      screen.getByRole("heading", { name: en.landing.hero_title }),
    ).toBeInTheDocument();
  });

  it("points the primary CTA at /login", () => {
    // QA E03/E05: this was a bare <button> with no onClick and no href — the landing
    // page's only call to action did nothing, and testers had to type /login by hand.
    renderLanding();

    const cta = screen.getByRole("link", { name: en.landing.cta_button });
    expect(cta).toHaveAttribute("href", "/login");
  });

  it("exposes the CTA as a link, not a button", () => {
    // Navigation must be a link: it has to be keyboard- and screen-reader-navigable,
    // and middle-click/open-in-new-tab must work.
    renderLanding();

    expect(
      screen.queryByRole("button", { name: en.landing.cta_button }),
    ).not.toBeInTheDocument();
  });
});
