/**
 * T-114 — Lecture wizard steps 1–2 + draft auto-save (Vitest + RTL).
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NextIntlClientProvider } from "next-intl";
import en from "../../../../../../messages/en/common.json";
import { LectureWizardClient } from "../LectureWizardClient";

vi.mock("@/hooks/use-client-auth", () => ({
  useClientAuth: () => ({ mounted: true, token: "tok" }),
}));

const listOfferings = vi.fn();
const listCurricula = vi.fn();
const listTopics = vi.fn();
const getDraft = vi.fn();
const upsertDraft = vi.fn();

vi.mock("@/lib/api", () => ({
  lectureWizardApi: {
    listOfferings: (...args: unknown[]) => listOfferings(...args),
    listCurricula: (...args: unknown[]) => listCurricula(...args),
    listTopics: (...args: unknown[]) => listTopics(...args),
    getDraft: (...args: unknown[]) => getDraft(...args),
    upsertDraft: (...args: unknown[]) => upsertDraft(...args),
  },
  ApiError: class ApiError extends Error {
    constructor(
      public status: number,
      public code: string,
      message: string
    ) {
      super(message);
    }
  },
}));

function renderWizard() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <NextIntlClientProvider locale="en" messages={en}>
        <LectureWizardClient />
      </NextIntlClientProvider>
    </QueryClientProvider>
  );
}

describe("LectureWizardClient", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getDraft.mockResolvedValue({
      id: null,
      teacher_user_id: "t-1",
      step: 1,
      data: {},
      updated_at: null,
    });
    listOfferings.mockResolvedValue([
      {
        id: "off-1",
        grade_id: "g-1",
        grade_name: "Grade 9",
        grade_level_ordinal: 9,
        subject_id: "s-1",
        subject_name: "Physics",
        academic_session: "2025-2026",
      },
    ]);
    listCurricula.mockResolvedValue([
      {
        id: "curr-1",
        title: "Punjab Physics 9",
        subject_id: "s-1",
        grade_level_ordinal: 9,
        is_primary: true,
        parse_degraded: false,
        topic_tree_jsonb: null,
      },
    ]);
    listTopics.mockResolvedValue({
      curriculum_id: "curr-1",
      parse_degraded: false,
      topics: [{ path: "Mechanics > Newton", label: "Newton" }],
    });
    upsertDraft.mockResolvedValue({
      id: "draft-1",
      teacher_user_id: "t-1",
      step: 2,
      data: {},
      updated_at: "2026-07-30T00:00:00Z",
    });
  });

  it("lists offerings and topics from the curriculum tree", async () => {
    const user = userEvent.setup();
    renderWizard();

    expect(await screen.findByRole("heading", { name: /Create a lecture/i })).toBeInTheDocument();
    const offering = await screen.findByLabelText(/Grade-Subject offering/i);
    await user.selectOptions(offering, "off-1");

    await waitFor(() => expect(listCurricula).toHaveBeenCalled());
    expect(await screen.findByText("Mechanics > Newton")).toBeInTheDocument();
    await user.click(screen.getByText("Mechanics > Newton"));
    await user.click(screen.getByRole("button", { name: /Continue/i }));

    expect(await screen.findByText(/Step 2 — Confirm curriculum/i)).toBeInTheDocument();
    expect(screen.getByText(/Primary/i)).toBeInTheDocument();
  });

  it("shows freeform topic when topic tree is degraded", async () => {
    const user = userEvent.setup();
    listTopics.mockResolvedValue({
      curriculum_id: "curr-1",
      parse_degraded: true,
      topics: [],
    });
    renderWizard();

    const offering = await screen.findByLabelText(/Grade-Subject offering/i);
    await user.selectOptions(offering, "off-1");

    expect(
      await screen.findByText(/topic tree is incomplete/i)
    ).toBeInTheDocument();
    expect(screen.getByLabelText(/Topic name/i)).toBeInTheDocument();
  });

  it("resumes at saved step from draft", async () => {
    getDraft.mockResolvedValue({
      id: "draft-1",
      teacher_user_id: "t-1",
      step: 2,
      data: {
        grade_subject_offering_id: "off-1",
        topic: "Newton",
        curriculum_id: "curr-1",
      },
      updated_at: "2026-07-30T00:00:00Z",
    });
    renderWizard();

    expect(await screen.findByText(/Step 2 — Confirm curriculum/i)).toBeInTheDocument();
    expect(screen.getByText(/Topic: Newton/i)).toBeInTheDocument();
  });
});
