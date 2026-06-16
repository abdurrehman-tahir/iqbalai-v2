import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NextIntlClientProvider } from "next-intl";
import { CurriculumItemDetail } from "../CurriculumItemDetail";
import en from "../../../../messages/en/common.json";

vi.mock("@/hooks/use-client-auth", () => ({
  useClientAuth: () => ({ mounted: true, token: "test-token" }),
}));

const getMock = vi.fn();
vi.mock("@/lib/api", () => ({
  schoolLibraryApi: {
    get: (...args: unknown[]) => getMock(...args),
  },
}));

function renderWithProviders(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <NextIntlClientProvider locale="en" messages={en}>
      <QueryClientProvider client={qc}>{ui}</QueryClientProvider>
    </NextIntlClientProvider>,
  );
}

describe("CurriculumItemDetail (T-058)", () => {
  it("shows available status and topic tree", async () => {
    getMock.mockResolvedValue({
      id: "item-1",
      title: "Punjab Physics Grade 9",
      content_type: "curriculum",
      language: "en",
      grade_level_ordinal: 9,
      ingestion_status: "available",
      visibility: "school_public",
      topic_tree_jsonb: {
        chapters: [
          {
            title: "Mechanics",
            sections: [{ title: "Motion", sub_topics: ["Speed"] }],
          },
        ],
        parse_degraded: false,
      },
    });

    renderWithProviders(
      <CurriculumItemDetail itemId="item-1" uploadHref="/coordinator/library/curriculum/upload" />,
    );

    expect(await screen.findByRole("status")).toHaveTextContent("Available");
    expect(screen.getByText("Mechanics")).toBeInTheDocument();
    expect(screen.getByText("School public")).toBeInTheDocument();
  });
});
