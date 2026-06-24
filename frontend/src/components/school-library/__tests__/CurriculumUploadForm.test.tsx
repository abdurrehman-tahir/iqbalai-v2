import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NextIntlClientProvider } from "next-intl";
import { CurriculumUploadForm } from "../CurriculumUploadForm";
import en from "../../../../messages/en/common.json";

const pushMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
}));

vi.mock("@/hooks/use-client-auth", () => ({
  useClientAuth: () => ({ mounted: true, token: "test-token" }),
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

describe("CurriculumUploadForm (T-058)", () => {
  beforeEach(() => {
    uploadMock.mockReset();
    pushMock.mockReset();
    uploadMock.mockResolvedValue({
      item: { id: "item-curriculum-1", title: "Punjab Physics Grade 9" },
    });
  });

  it("does not show a privacy toggle", async () => {
    renderWithProviders(<CurriculumUploadForm detailBasePath="/coordinator/library/curriculum" />);
    await waitFor(() => expect(screen.getByLabelText(/Subject/i)).toBeInTheDocument());
    expect(screen.queryByLabelText(/private/i)).not.toBeInTheDocument();
    expect(screen.getByText(/always visible to everyone/i)).toBeInTheDocument();
  });

  it("uploads curriculum with tags and redirects to detail page", async () => {
    const user = userEvent.setup();
    renderWithProviders(<CurriculumUploadForm detailBasePath="/coordinator/library/curriculum" />);

    await waitFor(() => expect(screen.getByLabelText(/Subject/i)).toBeInTheDocument());

    await user.type(screen.getByLabelText(/^Title/i), "Punjab Physics Grade 9");
    await user.selectOptions(screen.getByLabelText(/Subject/i), "subj-1");
    await user.selectOptions(screen.getByLabelText(/Grade/i), "9");
    await user.upload(
      screen.getByLabelText(/Curriculum PDF/i),
      new File(["%PDF-test"], "curriculum.pdf", { type: "application/pdf" }),
    );
    await user.click(screen.getByRole("button", { name: /Upload curriculum/i }));

    await waitFor(() => expect(uploadMock).toHaveBeenCalled());
    const [, params] = uploadMock.mock.calls[0];
    expect(params.content_type).toBe("curriculum");
    expect(params.subject_id).toBe("subj-1");
    expect(params.grade_level_ordinal).toBe(9);
    expect(params.visibility).toBeUndefined();
    expect(pushMock).toHaveBeenCalledWith("/coordinator/library/curriculum/item-curriculum-1");
  });
});
