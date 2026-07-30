import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NextIntlClientProvider } from "next-intl";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { ModeSwitcher } from "../ModeSwitcher";
import en from "../../../../messages/en/common.json";

vi.mock("@/hooks/use-client-auth", () => ({
  useClientAuth: () => ({ mounted: true, token: "tok" }),
}));

const getMode = vi.fn();
const setMode = vi.fn();

vi.mock("@/lib/api", () => ({
  studentModeApi: {
    getMode: (...args: unknown[]) => getMode(...args),
    setMode: (...args: unknown[]) => setMode(...args),
  },
}));

function renderSwitcher() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <NextIntlClientProvider locale="en" messages={en}>
        <ModeSwitcher />
      </NextIntlClientProvider>
    </QueryClientProvider>,
  );
}

describe("ModeSwitcher (T-101)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getMode.mockResolvedValue({
      active_mode: "lecture",
      mode_state: { lecture: { scroll_y: 10 }, self_study: {} },
      lecture_mode_enabled: true,
      self_study_mode_enabled: true,
    });
    setMode.mockResolvedValue({
      active_mode: "self_study",
      mode_state: { lecture: { scroll_y: 10 }, self_study: {} },
      lecture_mode_enabled: true,
      self_study_mode_enabled: true,
    });
  });

  it("shows loading skeleton then success radios", async () => {
    renderSwitcher();
    expect(screen.getByRole("status", { name: /Loading study mode/i })).toBeInTheDocument();
    expect(await screen.findByRole("radiogroup", { name: /Study mode/i })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: /Lecture/i })).toHaveAttribute("aria-checked", "true");
  });

  it("shows error + retry when get fails", async () => {
    getMode.mockRejectedValueOnce(new Error("boom"));
    renderSwitcher();
    expect(await screen.findByRole("alert")).toHaveTextContent(/Could not load study mode/i);
    expect(screen.getByRole("button", { name: /Retry/i })).toBeInTheDocument();
  });

  it("switches to Self-Study and passes leaving state", async () => {
    const user = userEvent.setup();
    renderSwitcher();
    await screen.findByRole("radiogroup", { name: /Study mode/i });
    await user.click(screen.getByRole("radio", { name: /Self-Study/i }));
    await waitFor(() => {
      expect(setMode).toHaveBeenCalledWith("tok", {
        active_mode: "self_study",
        leaving_mode_state: { scroll_y: 10 },
      });
    });
  });
});
