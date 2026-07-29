import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NextIntlClientProvider } from "next-intl";
import { ReferenceItemDetail } from "../ReferenceItemDetail";
import en from "../../../../messages/en/common.json";

const pushMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
}));

vi.mock("@/hooks/use-client-auth", () => ({
  useClientAuth: () => ({ mounted: true, token: "test-token" }),
}));

// T-245: ownership check now reads useCurrentUser() (GET /auth/me), not
// sessionStorage.
vi.mock("@/hooks/use-current-user", () => ({
  useCurrentUser: () => ({
    user: { user_id: "teacher-1", role: "teacher" },
    isLoading: false,
  }),
}));

const getMock = vi.fn();
const publishMock = vi.fn();
const removeSelectionMock = vi.fn();

vi.mock("@/lib/api", () => ({
  schoolLibraryApi: {
    get: (...args: unknown[]) => getMock(...args),
    publish: (...args: unknown[]) => publishMock(...args),
    removeSelection: (...args: unknown[]) => removeSelectionMock(...args),
  },
  ApiError: class ApiError extends Error {},
}));

function renderWithProviders(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <NextIntlClientProvider locale="en" messages={en}>
      <QueryClientProvider client={qc}>{ui}</QueryClientProvider>
    </NextIntlClientProvider>,
  );
}

const privateItem = {
  id: "ref-item-1",
  school_id: "school-1",
  title: "Physics Notes",
  content_type: "reference",
  language: "en",
  subject_id: null,
  grade_level_ordinal: null,
  storage_key: "school-library/school-1/notes.pdf",
  sha256: "a".repeat(64),
  ingestion_status: "available",
  topic_tree_jsonb: null,
  created_by: "teacher-1",
  visibility: "private",
  created_at: "2026-06-16T00:00:00Z",
  updated_at: "2026-06-16T00:00:00Z",
};

const publicItem = { ...privateItem, visibility: "school_public" };

describe("ReferenceItemDetail (T-059)", () => {
  beforeEach(() => {
    getMock.mockReset();
    publishMock.mockReset();
    removeSelectionMock.mockReset();
    pushMock.mockReset();
  });

  it("shows publish action for private items owned by the viewer", async () => {
    getMock.mockResolvedValue(privateItem);
    renderWithProviders(
      <ReferenceItemDetail
        itemId="ref-item-1"
        uploadHref="/teacher/library/reference/upload"
        libraryHref="/teacher/library"
      />,
    );

    await waitFor(() => expect(screen.getByText("Private — only you")).toBeInTheDocument());
    expect(screen.getByRole("button", { name: /Make available to school/i })).toBeInTheDocument();
  });

  it("publishes a private reference book", async () => {
    getMock.mockResolvedValue(privateItem);
    publishMock.mockResolvedValue(publicItem);
    const user = userEvent.setup();

    renderWithProviders(
      <ReferenceItemDetail
        itemId="ref-item-1"
        uploadHref="/teacher/library/reference/upload"
        libraryHref="/teacher/library"
      />,
    );

    await waitFor(() => expect(screen.getByRole("button", { name: /Make available to school/i })).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: /Make available to school/i }));

    await waitFor(() => expect(publishMock).toHaveBeenCalledWith("test-token", "ref-item-1"));
    expect(await screen.findByText(/now available to your school/i)).toBeInTheDocument();
  });

  it("shows unpublish blocked message for public items", async () => {
    getMock.mockResolvedValue(publicItem);
    renderWithProviders(
      <ReferenceItemDetail
        itemId="ref-item-1"
        uploadHref="/teacher/library/reference/upload"
        libraryHref="/teacher/library"
      />,
    );

    await waitFor(() => expect(screen.getByText("School public")).toBeInTheDocument());
    expect(screen.getByText(/cannot be made private/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Make available to school/i })).not.toBeInTheDocument();
  });

  it("removes selection for public items", async () => {
    getMock.mockResolvedValue(publicItem);
    removeSelectionMock.mockResolvedValue(publicItem);
    const user = userEvent.setup();

    renderWithProviders(
      <ReferenceItemDetail
        itemId="ref-item-1"
        uploadHref="/teacher/library/reference/upload"
        libraryHref="/teacher/library"
      />,
    );

    await waitFor(() => expect(screen.getByRole("button", { name: /Remove my selection/i })).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: /Remove my selection/i }));

    await waitFor(() => expect(removeSelectionMock).toHaveBeenCalledWith("test-token", "ref-item-1"));
    expect(pushMock).toHaveBeenCalledWith("/teacher/library/reference/upload");
  });
});
