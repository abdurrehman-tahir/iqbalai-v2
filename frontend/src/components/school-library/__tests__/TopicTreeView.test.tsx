import { render, screen } from "@testing-library/react";
import { TopicTreeView } from "../TopicTreeView";

describe("TopicTreeView (T-058)", () => {
  it("renders chapter section sub-topic hierarchy", () => {
    render(
      <TopicTreeView
        tree={{
          chapters: [
            {
              title: "Mechanics",
              sections: [{ title: "Motion", sub_topics: ["Speed", "Velocity"] }],
            },
          ],
        }}
        degradedLabel="degraded"
        emptyLabel="empty"
      />,
    );

    expect(screen.getByText("Mechanics")).toBeInTheDocument();
    expect(screen.getByText("Motion")).toBeInTheDocument();
    expect(screen.getByText("Speed")).toBeInTheDocument();
  });

  it("shows degraded message when tree is empty and degraded", () => {
    render(
      <TopicTreeView
        tree={{ chapters: [], parse_degraded: true }}
        degradedLabel="Parsing degraded"
        emptyLabel="No topics"
      />,
    );

    expect(screen.getByRole("status")).toHaveTextContent("Parsing degraded");
  });
});
