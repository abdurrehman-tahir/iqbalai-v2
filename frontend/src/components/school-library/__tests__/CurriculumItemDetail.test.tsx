import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NextIntlClientProvider } from "next-intl";
import { CurriculumItemDetail } from "../CurriculumItemDetail";
import en from "../../../../messages/en/common.json";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("@/hooks/use-client-auth", () => ({
  useClientAuth: () => ({ mounted: true, token: "test-token" }),
}));

// T-245: ownership check now reads useCurrentUser() (GET /auth/me), not
// sessionStorage.
vi.mock("@/hooks/use-current-user", () => ({
  useCurrentUser: () => ({ user: { user_id: "user-1" }, isLoading: false }),
}));

const getMock = vi.fn();
vi.mock("@/lib/api", () => ({
  schoolLibraryApi: {
    get: (...args: unknown[]) => getMock(...args),
    deleteItem: vi.fn(),
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
      created_by: "user-1",
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
      <CurriculumItemDetail
        itemId="item-1"
        uploadHref="/coordinator/library/curriculum/upload"
        libraryHref="/coordinator/curriculum"
      />,
    );

    expect(await screen.findByRole("status")).toHaveTextContent("Available");
    expect(screen.getByText("Mechanics")).toBeInTheDocument();
    expect(screen.getByText("School public")).toBeInTheDocument();
  });
});
