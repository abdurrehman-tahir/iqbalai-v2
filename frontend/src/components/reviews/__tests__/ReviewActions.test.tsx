import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactElement } from "react";
import { ReviewActions } from "../ReviewActions";
import { DETAIL } from "./review-fixtures";

vi.mock("next-intl", () => import("@/test/mocks/next-intl"));
vi.mock("@/hooks/use-client-auth", () => ({
  useClientAuth: () => ({ mounted: true, token: "test-token" }),
}));
const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

const api = {
  publishMini: vi.fn(),
  editMain: vi.fn(),
  dismiss: vi.fn(),
  reopen: vi.fn(),
};
class FakeApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}
vi.mock("@/lib/api", () => ({
  nextDayReviewApi: {
    publishMini: (...a: unknown[]) => api.publishMini(...a),
    editMain: (...a: unknown[]) => api.editMain(...a),
    dismiss: (...a: unknown[]) => api.dismiss(...a),
    reopen: (...a: unknown[]) => api.reopen(...a),
  },
  get ApiError() {
    return FakeApiError;
  },
}));

function renderWithClient(ui: ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

beforeEach(() => vi.clearAllMocks());

describe("ReviewActions", () => {
  it("renders nothing for viewers who cannot act", () => {
    const { container } = renderWithClient(
      <ReviewActions review={{ ...DETAIL, can_act: false }} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("publish triggers targeted distribution", async () => {
    api.publishMini.mockResolvedValue({ ...DETAIL, mini_published: true });
    renderWithClient(<ReviewActions review={DETAIL} />);
    await userEvent.click(screen.getByRole("button", { name: "publish" }));
    expect(api.publishMini).toHaveBeenCalledWith("test-token", "rev-1");
  });

  it("publish is disabled once published or without a mini", () => {
    const { rerender } = renderWithClient(
      <ReviewActions review={{ ...DETAIL, mini_published: true }} />,
    );
    expect(screen.getByRole("button", { name: "published" })).toBeDisabled();
    rerender(
      <QueryClientProvider client={new QueryClient()}>
        <ReviewActions review={{ ...DETAIL, mini_lecture_id: null }} />
      </QueryClientProvider>,
    );
    expect(screen.getByRole("button", { name: "publish" })).toBeDisabled();
  });

  it("edit main records the action then opens Flow 5 edit mode with context", async () => {
    api.editMain.mockResolvedValue(DETAIL);
    renderWithClient(<ReviewActions review={DETAIL} />);
    await userEvent.click(screen.getByRole("button", { name: "edit_main" }));
    expect(api.editMain).toHaveBeenCalledWith("test-token", "rev-1");
    expect(push).toHaveBeenCalledWith("/teacher/lectures/lec-1?from_review=rev-1");
  });

  it("schedule group study is present but disabled (Flow 11 pending)", () => {
    renderWithClient(<ReviewActions review={DETAIL} />);
    expect(screen.getByRole("button", { name: "group_study" })).toBeDisabled();
  });

  it("dismiss and reopen", async () => {
    api.dismiss.mockResolvedValue({ ...DETAIL, status: "dismissed" });
    const { rerender } = renderWithClient(<ReviewActions review={DETAIL} />);
    await userEvent.click(screen.getByRole("button", { name: "dismiss" }));
    expect(api.dismiss).toHaveBeenCalledWith("test-token", "rev-1");

    api.reopen.mockResolvedValue(DETAIL);
    rerender(
      <QueryClientProvider client={new QueryClient()}>
        <ReviewActions review={{ ...DETAIL, status: "dismissed" }} />
      </QueryClientProvider>,
    );
    await userEvent.click(screen.getByRole("button", { name: "reopen" }));
    expect(api.reopen).toHaveBeenCalledWith("test-token", "rev-1");
  });

  it("explains a PRECONDITION_FAILED publish (no enrolled recipients)", async () => {
    api.publishMini.mockRejectedValue(new FakeApiError(412, "PRECONDITION_FAILED", "none"));
    renderWithClient(<ReviewActions review={DETAIL} />);
    await userEvent.click(screen.getByRole("button", { name: "publish" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("publish_no_recipients");
  });
});
