import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactElement } from "react";
import { BulkImportClient } from "../BulkImportClient";

vi.mock("next-intl", () => import("@/test/mocks/next-intl"));

const mockAuth = vi.fn<() => { mounted: boolean; token: string | null }>(() => ({
  mounted: true,
  token: "test-token",
}));
vi.mock("@/hooks/use-client-auth", () => ({
  useClientAuth: () => mockAuth(),
}));

const dryRunMock = vi.fn();
const commitMock = vi.fn();
vi.mock("@/lib/api", () => ({
  bulkImportApi: {
    dryRun: (...a: unknown[]) => dryRunMock(...a),
    commit: (...a: unknown[]) => commitMock(...a),
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
});

describe("BulkImportClient", () => {
  it("runs dry-run then commits valid rows", async () => {
    const user = userEvent.setup();
    dryRunMock.mockResolvedValue({
      id: "job-1",
      total_rows: 2,
      success_rows: 1,
      failed_rows: 1,
      status: "dry_run_complete",
      rows: [
        {
          row_number: 2,
          status: "valid",
          errors: [],
          data: { name: "Alice", email: "a@test.com", grade: "Grade 9" },
        },
        {
          row_number: 3,
          status: "invalid",
          errors: ["grade_out_of_scope"],
          data: { name: "Bob", email: "b@test.com", grade: "Grade 11" },
        },
      ],
    });
    commitMock.mockResolvedValue({
      id: "job-1",
      total_rows: 2,
      success_rows: 1,
      failed_rows: 1,
      status: "committed_with_errors",
      rows: [
        { row_number: 2, status: "enrolled", errors: [], data: { name: "Alice" } },
        { row_number: 3, status: "invalid", errors: ["grade_out_of_scope"], data: {} },
      ],
    });

    renderWithClient(<BulkImportClient />);

    const file = new File(["name,email,grade\n"], "students.csv", { type: "text/csv" });
    const input = document.getElementById("bulk-import-file") as HTMLInputElement;
    await user.upload(input, file);
    await user.click(screen.getByRole("button", { name: "run_dry_run" }));

    await waitFor(() => expect(dryRunMock).toHaveBeenCalledWith("test-token", file));
    await waitFor(() => expect(screen.getByText("results_title")).toBeInTheDocument());

    await user.click(screen.getByRole("button", { name: "commit_button" }));
    await waitFor(() => expect(commitMock).toHaveBeenCalledWith("test-token", "job-1"));
    await waitFor(() => expect(screen.getByText("commit_partial")).toBeInTheDocument());
  });
});
