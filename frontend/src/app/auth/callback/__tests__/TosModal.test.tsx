import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TosModal } from "../TosModal";

vi.mock("next-intl", () => import("@/test/mocks/next-intl"));

const SHORT_TOS = { id: "t1", version: 1, content: "Short terms." };
const LONG_TOS = {
  id: "t2",
  version: 2,
  content: Array.from({ length: 60 }, (_, i) => `Line ${i}`).join("\n"),
};

describe("TosModal (T-232)", () => {
  const onAccept = vi.fn().mockResolvedValue(undefined);
  const onDecline = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders ToS content", () => {
    render(<TosModal tos={SHORT_TOS} onAccept={onAccept} onDecline={onDecline} />);
    expect(screen.getByText("Short terms.")).toBeInTheDocument();
  });

  it("enables Accept immediately when content fits without scrolling", async () => {
    render(<TosModal tos={SHORT_TOS} onAccept={onAccept} onDecline={onDecline} />);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "accept" })).not.toBeDisabled(),
    );
  });

  it("enables Accept after scrolling to the bottom of long content", async () => {
    render(<TosModal tos={LONG_TOS} onAccept={onAccept} onDecline={onDecline} />);
    const acceptBtn = screen.getByRole("button", { name: "accept" });
    const content = screen.getByLabelText("content_label") as HTMLDivElement;
    Object.defineProperty(content, "scrollHeight", { value: 2000, configurable: true });
    Object.defineProperty(content, "clientHeight", { value: 400, configurable: true });
    Object.defineProperty(content, "scrollTop", { value: 1600, writable: true, configurable: true });
    fireEvent.scroll(content);
    await waitFor(() => expect(acceptBtn).not.toBeDisabled());
  });

  it("shows empty placeholder when content is blank", () => {
    render(
      <TosModal tos={{ id: "t0", version: 0, content: "   " }} onAccept={onAccept} onDecline={onDecline} />,
    );
    expect(screen.getByText("empty_content")).toBeInTheDocument();
  });

  it("calls onAccept when accept is clicked on short content", async () => {
    const user = userEvent.setup();
    render(<TosModal tos={SHORT_TOS} onAccept={onAccept} onDecline={onDecline} />);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "accept" })).not.toBeDisabled(),
    );
    await user.click(screen.getByRole("button", { name: "accept" }));
    await waitFor(() => expect(onAccept).toHaveBeenCalledOnce());
  });

  it("calls onDecline when decline is clicked", async () => {
    const user = userEvent.setup();
    render(<TosModal tos={SHORT_TOS} onAccept={onAccept} onDecline={onDecline} />);
    await user.click(screen.getByRole("button", { name: "decline" }));
    expect(onDecline).toHaveBeenCalledOnce();
  });
});
