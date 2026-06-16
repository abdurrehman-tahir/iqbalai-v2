import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NextIntlClientProvider } from "next-intl";
import { LibraryIngestionPanel } from "../LibraryIngestionPanel";
import en from "../../../../messages/en/common.json";

vi.mock("@/hooks/use-client-auth", () => ({
  useClientAuth: () => ({ token: "test-token" }),
}));

const retryMock = vi.fn();
vi.mock("@/lib/api", () => ({
  schoolLibraryApi: {
    retryIngestion: (...args: unknown[]) => retryMock(...args),
  },
  ApiError: class ApiError extends Error {},
}));

function renderWithProviders(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  return render(
    <NextIntlClientProvider locale="en" messages={en}>
      <QueryClientProvider client={qc}>{ui}</QueryClientProvider>
    </NextIntlClientProvider>,
  );
}

describe("LibraryIngestionPanel (T-061)", () => {
  beforeEach(() => {
    retryMock.mockReset();
    retryMock.mockResolvedValue({
      id: "item-1",
      ingestion_status: "pending",
      ingestion_error: null,
    });
  });

  it("shows failure reason and retry button", () => {
    renderWithProviders(
      <LibraryIngestionPanel
        itemId="item-1"
        item={{ ingestion_status: "failed", ingestion_error: "MinIO down" }}
      />,
    );

    expect(screen.getByText("MinIO down")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Retry ingestion/i })).toBeInTheDocument();
  });

  it("calls retry ingestion API", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <LibraryIngestionPanel
        itemId="item-1"
        item={{ ingestion_status: "failed", ingestion_error: "MinIO down" }}
      />,
    );

    await user.click(screen.getByRole("button", { name: /Retry ingestion/i }));

    await waitFor(() =>
      expect(retryMock).toHaveBeenCalledWith("test-token", "item-1"),
    );
  });
});
