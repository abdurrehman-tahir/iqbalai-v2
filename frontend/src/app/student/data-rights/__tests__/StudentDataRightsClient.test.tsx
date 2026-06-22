import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NextIntlClientProvider } from "next-intl";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { StudentDataRightsClient } from "../StudentDataRightsClient";
import en from "../../../../../messages/en/common.json";

vi.mock("@/hooks/use-client-auth", () => ({
  useClientAuth: () => ({ mounted: true, token: "tok" }),
}));

vi.mock("@/lib/api", () => ({
  dataRightsApi: {
    getStudentStatus: vi.fn().mockResolvedValue({
      export_policy_message: "Export policy",
      deletion_policy_message: "Deletion policy",
      export_request: null,
      deletion_request: null,
    }),
    requestStudentExport: vi.fn().mockResolvedValue({ id: "exp-1", status: "requested" }),
    requestStudentDeletion: vi.fn().mockResolvedValue({ id: "del-1", status: "grace_period" }),
    cancelStudentDeletion: vi.fn(),
    downloadStudentExport: vi.fn(),
  },
}));

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <NextIntlClientProvider locale="en" messages={en}>
        <StudentDataRightsClient />
      </NextIntlClientProvider>
    </QueryClientProvider>,
  );
}

describe("StudentDataRightsClient (T-084)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows PDPB messaging and requests export", async () => {
    const user = userEvent.setup();
    const { dataRightsApi } = await import("@/lib/api");
    renderPage();

    expect(await screen.findByText(/PDPB 2025/i)).toBeInTheDocument();
    expect(screen.getByText(/Request a ZIP bundle/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Request export/i }));

    await waitFor(() => {
      expect(dataRightsApi.requestStudentExport).toHaveBeenCalledWith("tok");
    });
  });
});
