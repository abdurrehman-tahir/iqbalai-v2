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
vi.mock("@/lib/api", () => ({
  bulkImportApi: {
    dryRun: (...a: unknown[]) => dryRunMock(...a),
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
  it("runs dry-run and shows row results with disabled commit", async () => {
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

    renderWithClient(<BulkImportClient />);

    const file = new File(["name,email,grade\n"], "students.csv", { type: "text/csv" });
    const input = document.getElementById("bulk-import-file") as HTMLInputElement;
    await user.upload(input, file);
    await user.click(screen.getByRole("button", { name: "run_dry_run" }));

    await waitFor(() => expect(dryRunMock).toHaveBeenCalledWith("test-token", file));
    await waitFor(() => expect(screen.getByText("results_title")).toBeInTheDocument());
    expect(screen.getByRole("button", { name: "commit_disabled" })).toBeDisabled();
  });
});
