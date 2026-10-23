import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactElement } from "react";
import { ReflectivePrompt } from "../ReflectivePrompt";
import { DETAIL } from "./review-fixtures";

vi.mock("next-intl", () => import("@/test/mocks/next-intl"));
vi.mock("@/hooks/use-client-auth", () => ({
  useClientAuth: () => ({ mounted: true, token: "test-token" }),
}));

const reflect = vi.fn();
const transcribeVoice = vi.fn();
vi.mock("@/lib/api", () => ({
  nextDayReviewApi: { reflect: (...a: unknown[]) => reflect(...a) },
  lectureWizardApi: { transcribeVoice: (...a: unknown[]) => transcribeVoice(...a) },
}));

// The canonical widget has its own tests; stub it to a single submit button.
// Like the real widget, the stub swallows a rejected onSubmit (it shows its own error).
vi.mock("@/components/shared/HybridInputWidget", () => ({
  HybridInputWidget: (props: {
    onSubmit: (p: { text: string; attached_images: [] }) => Promise<void>;
    transcribeAudio?: (b: Blob, l?: string) => Promise<unknown>;
  }) => (
    <div>
      <button
        onClick={() =>
          void props
            .onSubmit({ text: " I'll use a demo. ", attached_images: [] })
            .catch(() => undefined)
        }
      >
        send
      </button>
      <button onClick={() => void props.transcribeAudio?.(new Blob(["x"]), "ur")}>voice</button>
    </div>
  ),
}));

function renderWithClient(ui: ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

beforeEach(() => vi.clearAllMocks());

describe("ReflectivePrompt", () => {
  it("renders nothing when the review has no reflective question", () => {
    const { container } = renderWithClient(
      <ReflectivePrompt review={{ ...DETAIL, reflective_prompt: "" }} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("owner submits a typed answer", async () => {
    reflect.mockResolvedValue({ ...DETAIL, reflected: true });
    renderWithClient(<ReflectivePrompt review={DETAIL} />);
    expect(screen.getByText(DETAIL.reflective_prompt)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "send" }));
    expect(reflect).toHaveBeenCalledWith("test-token", "rev-1", { response: "I'll use a demo." });
  });

  it("voice answers go through the teacher lecture transcribe endpoint", async () => {
    transcribeVoice.mockResolvedValue({ transcript: "hi" });
    renderWithClient(<ReflectivePrompt review={DETAIL} />);
    await userEvent.click(screen.getByRole("button", { name: "voice" }));
    expect(transcribeVoice).toHaveBeenCalledWith("test-token", "lec-1", expect.any(Blob), "ur");
  });

  it("shows the saved state once reflected", () => {
    renderWithClient(<ReflectivePrompt review={{ ...DETAIL, reflected: true }} />);
    expect(screen.getByRole("status")).toHaveTextContent("saved");
    expect(screen.queryByRole("button", { name: "send" })).not.toBeInTheDocument();
  });

  it("non-owners see the question but cannot answer", () => {
    renderWithClient(<ReflectivePrompt review={{ ...DETAIL, is_owner: false }} />);
    expect(screen.getByText(DETAIL.reflective_prompt)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "send" })).not.toBeInTheDocument();
  });

  it("surfaces a save error", async () => {
    reflect.mockRejectedValue(new Error("500"));
    renderWithClient(<ReflectivePrompt review={DETAIL} />);
    await userEvent.click(screen.getByRole("button", { name: "send" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("error");
  });
});
