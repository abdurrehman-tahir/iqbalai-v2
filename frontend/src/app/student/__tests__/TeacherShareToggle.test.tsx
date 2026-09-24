import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NextIntlClientProvider } from "next-intl";
import { TeacherShareToggle } from "../lectures/[lectureId]/TeacherShareToggle";

const getTeacherShare = vi.fn();
const setTeacherShare = vi.fn();

vi.mock("@/lib/api", () => ({
  studentPrivacyApi: {
    getTeacherShare: (...args: unknown[]) => getTeacherShare(...args),
    setTeacherShare: (...args: unknown[]) => setTeacherShare(...args),
  },
}));

const messages = {
  student: {
    lecture_viewer: {
      privacy_share_label: "Share study questions with my teacher",
      privacy_share_help: "When off, teachers cannot see your lecture questions.",
    },
  },
};

function wrap(ui: React.ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return (
    <QueryClientProvider client={client}>
      <NextIntlClientProvider locale="en" messages={messages}>
        {ui}
      </NextIntlClientProvider>
    </QueryClientProvider>
  );
}

describe("TeacherShareToggle", () => {
  beforeEach(() => {
    getTeacherShare.mockReset();
    setTeacherShare.mockReset();
    getTeacherShare.mockResolvedValue({ teacher_activity_share: "share" });
    setTeacherShare.mockResolvedValue({ teacher_activity_share: "private" });
  });

  it("defaults to checked (share) and opts out on toggle", async () => {
    render(wrap(<TeacherShareToggle token="tok" />));
    const checkbox = await screen.findByRole("checkbox");
    expect(checkbox).toBeChecked();

    fireEvent.click(checkbox);
    await waitFor(() => {
      expect(setTeacherShare).toHaveBeenCalledWith("tok", "private");
    });
  });
});
