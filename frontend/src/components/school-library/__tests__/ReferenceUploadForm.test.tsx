import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NextIntlClientProvider } from "next-intl";
import { ReferenceUploadForm } from "../ReferenceUploadForm";
import en from "../../../../messages/en/common.json";

const pushMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
}));

vi.mock("@/hooks/use-client-auth", () => ({
  useClientAuth: () => ({ mounted: true, token: "test-token" }),
}));

vi.mock("@/lib/auth", () => ({
  getUser: () => ({ user_id: "teacher-1", role: "teacher" }),
}));

const uploadMock = vi.fn();
vi.mock("@/lib/api", () => ({
  subjectsApi: {
    list: vi.fn().mockResolvedValue([{ id: "subj-1", name: "Physics" }]),
  },
  gradesApi: {
    list: vi.fn().mockResolvedValue([{ id: "grade-9", name: "Grade 9", level_ordinal: 9 }]),
  },
  schoolLibraryApi: {
    upload: (...args: unknown[]) => uploadMock(...args),
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

describe("ReferenceUploadForm (T-059)", () => {
  beforeEach(() => {
    uploadMock.mockReset();
    pushMock.mockReset();
    uploadMock.mockResolvedValue({
      item: { id: "ref-item-1", title: "Physics Notes", visibility: "private" },
    });
  });

  it("defaults privacy toggle to unchecked (private upload)", async () => {
    renderWithProviders(<ReferenceUploadForm detailBasePath="/teacher/library/reference" />);
    await waitFor(() => expect(screen.getByLabelText(/Make available to the school/i)).toBeInTheDocument());
    expect(screen.getByLabelText(/Make available to the school/i)).not.toBeChecked();
  });

  it("uploads private reference by default and redirects to detail", async () => {
    const user = userEvent.setup();
    renderWithProviders(<ReferenceUploadForm detailBasePath="/teacher/library/reference" />);

    await waitFor(() => expect(screen.getByLabelText(/Subject/i)).toBeInTheDocument());

    await user.type(screen.getByLabelText(/^Title/i), "Physics Notes");
    await user.upload(
      screen.getByLabelText(/Reference PDF/i),
      new File(["%PDF-test"], "notes.pdf", { type: "application/pdf" }),
    );
    await user.click(screen.getByRole("button", { name: /Upload reference book/i }));

    await waitFor(() => expect(uploadMock).toHaveBeenCalled());
    const [, params] = uploadMock.mock.calls[0];
    expect(params.content_type).toBe("reference");
    expect(params.visibility).toBeUndefined();
    expect(pushMock).toHaveBeenCalledWith("/teacher/library/reference/ref-item-1");
  });

  it("sends school_public when privacy toggle is checked", async () => {
    const user = userEvent.setup();
    renderWithProviders(<ReferenceUploadForm detailBasePath="/teacher/library/reference" />);

    await waitFor(() => expect(screen.getByLabelText(/Make available to the school/i)).toBeInTheDocument());

    await user.type(screen.getByLabelText(/^Title/i), "Shared Notes");
    await user.click(screen.getByLabelText(/Make available to the school/i));
    await user.upload(
      screen.getByLabelText(/Reference PDF/i),
      new File(["%PDF-test"], "notes.pdf", { type: "application/pdf" }),
    );
    await user.click(screen.getByRole("button", { name: /Upload reference book/i }));

    await waitFor(() => expect(uploadMock).toHaveBeenCalled());
    const [, params] = uploadMock.mock.calls[0];
    expect(params.visibility).toBe("school_public");
  });
});
