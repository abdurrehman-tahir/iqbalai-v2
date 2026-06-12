import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "../card";

// T-226 — the Card primitive must render through the semantic design-token
// classes (bg-card, border-border, text-card-foreground, text-muted-foreground)
// and must NOT carry any ad-hoc palette literals or inline styles.

describe("Card — design tokens (T-226)", () => {
  it("renders surface + border via semantic token classes", () => {
    const { container } = render(<Card>content</Card>);
    const card = container.firstElementChild as HTMLElement;
    expect(card.className).toContain("bg-card");
    expect(card.className).toContain("border-border");
    expect(card.className).toContain("text-card-foreground");
  });

  it("uses muted-foreground for the description, not a gray literal", () => {
    const { container } = render(<CardDescription>desc</CardDescription>);
    const el = container.firstElementChild as HTMLElement;
    expect(el.className).toContain("text-muted-foreground");
  });

  it("carries no ad-hoc palette literals", () => {
    const { container } = render(
      <Card>
        <CardHeader>
          <CardTitle>Title</CardTitle>
          <CardDescription>Desc</CardDescription>
        </CardHeader>
        <CardContent>Body</CardContent>
      </Card>,
    );
    const html = container.innerHTML;
    expect(html).not.toMatch(/bg-white/);
    expect(html).not.toMatch(/text-gray-/);
    expect(html).not.toMatch(/border-gray-/);
  });

  it("renders no inline styles", () => {
    const { container } = render(
      <Card>
        <CardContent>Body</CardContent>
      </Card>,
    );
    expect(container.querySelectorAll("[style]")).toHaveLength(0);
  });

  it("matches the tokenized snapshot", () => {
    const { container } = render(
      <Card>
        <CardHeader>
          <CardTitle>Title</CardTitle>
          <CardDescription>Desc</CardDescription>
        </CardHeader>
        <CardContent>Body</CardContent>
      </Card>,
    );
    expect(container.firstChild).toMatchSnapshot();
  });
});
