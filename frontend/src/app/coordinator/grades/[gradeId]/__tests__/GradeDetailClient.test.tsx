import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactElement } from "react";
import { GradeDetailClient } from "../GradeDetailClient";

vi.mock("next-intl", () => import("@/test/mocks/next-intl"));
vi.mock("next/navigation", () => ({
  useParams: () => ({ gradeId: "grade-9" }),
}));
vi.mock("next/link", () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

const mockAuth = vi.fn(() => ({ mounted: true, token: "test-token" }));
vi.mock("@/hooks/use-client-auth", () => ({
  useClientAuth: () => mockAuth(),
}));

const getGradeMock = vi.fn();
const listSectionsMock = vi.fn();
const listOfferingsMock = vi.fn();
const listSubjectsMock = vi.fn();
const getMeMock = vi.fn();
const enrollMock = vi.fn();

vi.mock("@/lib/api", () => ({
  gradesApi: { get: (...a: unknown[]) => getGradeMock(...a) },
  sectionsApi: { list: (...a: unknown[]) => listSectionsMock(...a) },
  offeringsApi: {
    list: (...a: unknown[]) => listOfferingsMock(...a),
    eligibleTeachers: vi.fn(),
  },
  subjectsApi: { list: (...a: unknown[]) => listSubjectsMock(...a) },
  usersApi: { getMe: (...a: unknown[]) => getMeMock(...a) },
  studentEnrollmentsApi: { enroll: (...a: unknown[]) => enrollMock(...a) },
  ApiError: class ApiError extends Error {
    constructor(public status: number) {
      super("api error");
    }
  },
}));

function renderWithClient(ui: ReactElement) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

beforeEach(() => {
  vi.clearAllMocks();
  getGradeMock.mockResolvedValue({
    id: "grade-9",
    name: "Grade 9",
    academic_session: "2025-2026",
  });
  listSectionsMock.mockResolvedValue([
    { id: "section-a", name: "A", grade_id: "grade-9", status: "active" },
  ]);
  listOfferingsMock.mockResolvedValue([]);
  listSubjectsMock.mockResolvedValue([]);
  getMeMock.mockResolvedValue({ role: "coordinator" });
  enrollMock.mockResolvedValue({ id: "enr-1" });
});

describe("GradeDetailClient enrollment", () => {
  it("enrolls a student into a section", async () => {
    const user = userEvent.setup();
    renderWithClient(<GradeDetailClient />);

    await waitFor(() => expect(screen.getByText("Grade 9")).toBeInTheDocument());

    await user.click(screen.getByLabelText("sections.enroll_button"));
    await user.type(screen.getByLabelText("sections.enroll_modal.name_label"), "Ali Khan");
    await user.type(screen.getByLabelText("sections.enroll_modal.email_label"), "ali@school.edu");
    await user.click(screen.getByRole("button", { name: "sections.enroll_modal.submit" }));

    await waitFor(() =>
      expect(enrollMock).toHaveBeenCalledWith("test-token", "grade-9", {
        display_name: "Ali Khan",
        email: "ali@school.edu",
        section_id: "section-a",
      }),
    );
  });
});
