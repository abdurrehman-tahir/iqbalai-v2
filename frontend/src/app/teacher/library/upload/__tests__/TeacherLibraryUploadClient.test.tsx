import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NextIntlClientProvider } from "next-intl";
import { TeacherLibraryUploadClient } from "../TeacherLibraryUploadClient";
import en from "../../../../../../messages/en/common.json";

vi.mock("@/hooks/use-client-auth", () => ({
  useClientAuth: () => ({ mounted: true, token: "test-token" }),
}));

const uploadMock = vi.fn();
vi.mock("@/lib/api", () => ({
  schoolLibraryApi: {
    upload: (...args: unknown[]) => uploadMock(...args),
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

describe("TeacherLibraryUploadClient (T-055)", () => {
  beforeEach(() => {
    uploadMock.mockReset();
    uploadMock.mockResolvedValue({
      item: { title: "Physics Notes", ingestion_status: "pending" },
      storage_deduplicated: false,
      selection_created: true,
      message: "ok",
    });
  });

  it("renders upload form", () => {
    renderWithProviders(<TeacherLibraryUploadClient />);
    expect(screen.getByLabelText(/Title/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/PDF file/i)).toBeInTheDocument();
  });

  it("submits a PDF upload", async () => {
    const user = userEvent.setup();
    renderWithProviders(<TeacherLibraryUploadClient />);

    await user.type(screen.getByLabelText(/Title/i), "Physics Notes");
    const fileInput = screen.getByLabelText(/PDF file/i);
    await user.upload(
      fileInput,
      new File(["%PDF-test"], "notes.pdf", { type: "application/pdf" }),
    );
    await user.click(screen.getByRole("button", { name: /Upload PDF/i }));

    expect(uploadMock).toHaveBeenCalled();
    expect(await screen.findByRole("status")).toHaveTextContent("pending ingestion");
  });
});
