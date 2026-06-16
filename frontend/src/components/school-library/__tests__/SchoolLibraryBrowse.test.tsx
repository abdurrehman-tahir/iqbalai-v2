import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NextIntlClientProvider } from "next-intl";
import { SchoolLibraryBrowse } from "../SchoolLibraryBrowse";
import en from "../../../../messages/en/common.json";

vi.mock("@/hooks/use-client-auth", () => ({
  useClientAuth: () => ({ mounted: true, token: "test-token" }),
}));

const listMock = vi.fn();
vi.mock("@/lib/api", () => ({
  subjectsApi: {
    list: vi.fn().mockResolvedValue([{ id: "subj-1", name: "Physics" }]),
  },
  gradesApi: {
    list: vi.fn().mockResolvedValue([{ id: "grade-9", name: "Grade 9", level_ordinal: 9 }]),
  },
  schoolLibraryApi: {
    list: (...args: unknown[]) => listMock(...args),
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

describe("SchoolLibraryBrowse (T-060)", () => {
  beforeEach(() => {
    listMock.mockReset();
    listMock.mockResolvedValue({
      items: [
        {
          id: "item-public",
          title: "Punjab Physics Grade 9",
          content_type: "curriculum",
          visibility: "school_public",
          ingestion_status: "available",
          language: "en",
          grade_level_ordinal: 9,
        },
        {
          id: "item-private",
          title: "My Notes",
          content_type: "reference",
          visibility: "private",
          ingestion_status: "pending",
          language: "en",
          grade_level_ordinal: null,
        },
      ],
      total: 2,
    });
  });

  it("lists visible library items with status badges", async () => {
    renderWithProviders(<SchoolLibraryBrowse />);

    await waitFor(() => expect(screen.getByText("Punjab Physics Grade 9")).toBeInTheDocument());
    expect(screen.getByText("My Notes")).toBeInTheDocument();
    expect(screen.getByText("Available")).toBeInTheDocument();
    expect(screen.getByText("Pending")).toBeInTheDocument();
  });

  it("passes combinable filters to the list API", async () => {
    renderWithProviders(<SchoolLibraryBrowse />);

    await waitFor(() => expect(document.getElementById("library-subject")).not.toBeNull());

    fireEvent.change(screen.getByLabelText(/Search by title/i), {
      target: { value: "Physics" },
    });
    fireEvent.change(document.getElementById("library-subject")!, { target: { value: "subj-1" } });
    fireEvent.change(document.getElementById("library-grade")!, { target: { value: "9" } });
    fireEvent.change(document.getElementById("library-language")!, { target: { value: "en" } });
    fireEvent.change(document.getElementById("library-content-type")!, {
      target: { value: "curriculum" },
    });

    await waitFor(() => {
      const lastCall = listMock.mock.calls.at(-1);
      expect(lastCall?.[1]).toMatchObject({
        title: "Physics",
        subject_id: "subj-1",
        grade_level_ordinal: 9,
        language: "en",
        content_type: "curriculum",
      });
    });
  });
});
