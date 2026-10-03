/** T-188 — My Highlights: four UI states, flashcard flip/edit, delete, deep link. */
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NextIntlClientProvider } from "next-intl";
import type { MyHighlightRead, MyHighlightsPage } from "@/lib/api";
import enMessages from "../../../../../messages/en/common.json";
import urMessages from "../../../../../messages/ur/common.json";
import { MyHighlightsClient } from "../MyHighlightsClient";
import { lecturePositionHref } from "../HighlightCard";

const listMine = vi.fn();
const updateBack = vi.fn();
const deleteHighlight = vi.fn();

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ApiError: actual.ApiError,
    studentHighlightsApi: {
      listMine: (...a: unknown[]) => listMine(...a),
      updateFlashcardBack: (...a: unknown[]) => updateBack(...a),
      deleteHighlight: (...a: unknown[]) => deleteHighlight(...a),
    },
  };
});

vi.mock("@/hooks/use-client-auth", () => ({
  useClientAuth: () => ({ mounted: true, token: "tok" }),
}));

function item(overrides: Partial<MyHighlightRead> = {}): MyHighlightRead {
  return {
    id: "h-1",
    highlighted_text: "mass",
    concept_tag: "forces/newton-2",
    created_at: "2026-10-03T12:00:00Z",
    lecture: { id: "lec-1", title: "Newton's Laws", topic: "Forces" },
    paragraph_ordinal: 0,
    question_id: "q-1",
    flashcard: {
      id: "fc-1",
      front_text: "mass",
      back_text: "Mass is the amount of matter.",
      back_is_placeholder: false,
      status: "active",
      concept_tag: "forces/newton-2",
      created_at: "2026-10-03T12:00:01Z",
    },
    ...overrides,
  };
}

function pageOf(
  items: MyHighlightRead[],
  pages = 1,
  page = 1,
): MyHighlightsPage {
  return { items, total: items.length, page, page_size: 20, pages };
}

function renderClient(locale: "en" | "ur" = "en") {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <NextIntlClientProvider
        locale={locale}
        messages={locale === "en" ? enMessages : urMessages}
        timeZone="UTC"
      >
        <MyHighlightsClient />
      </NextIntlClientProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  listMine.mockReset();
  updateBack.mockReset();
  deleteHighlight.mockReset();
});

describe("MyHighlightsClient — four UI states", () => {
  it("loading: renders skeletons", () => {
    listMine.mockReturnValue(new Promise(() => {}));
    renderClient();
    expect(screen.getByTestId("my-highlights-loading")).toHaveAttribute(
      "aria-busy",
      "true",
    );
  });

  it("empty: explains how to create highlights and links to lectures", async () => {
    listMine.mockResolvedValue(pageOf([]));
    renderClient();
    expect(await screen.findByText("No highlights yet")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Go to my lectures" }),
    ).toHaveAttribute("href", "/student");
  });

  it("error: shows an alert with a working retry", async () => {
    listMine.mockRejectedValueOnce(new Error("down"));
    listMine.mockResolvedValue(pageOf([item()]));
    renderClient();
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Could not load your highlights.");
    fireEvent.click(within(alert).getByRole("button", { name: "Try again" }));
    expect(await screen.findByTestId("my-highlight")).toBeInTheDocument();
  });

  it("success: lists highlight with lecture, concept, link and flashcard", async () => {
    listMine.mockResolvedValue(pageOf([item()]));
    renderClient();
    const row = await screen.findByTestId("my-highlight");
    expect(
      within(row).getByText("mass", { selector: "mark" }),
    ).toBeInTheDocument();
    expect(within(row).getByTestId("my-highlight-lecture")).toHaveTextContent(
      "Lecture: Newton's Laws",
    );
    expect(within(row).getByTestId("my-highlight-concept")).toHaveTextContent(
      "Concept: forces/newton-2",
    );
    expect(within(row).getByTestId("my-highlight-open")).toHaveAttribute(
      "href",
      "/student/lectures/lec-1?highlight=h-1",
    );
    expect(within(row).getByTestId("flashcard-front")).toHaveTextContent(
      "mass",
    );
    expect(listMine).toHaveBeenCalledWith("tok", 1, 20);
  });
});

describe("HighlightCard interactions", () => {
  it("flips the flashcard to show the answer", async () => {
    listMine.mockResolvedValue(pageOf([item()]));
    renderClient();
    const flip = await screen.findByTestId("flashcard-flip");
    expect(flip).toHaveAttribute("aria-pressed", "false");
    fireEvent.click(flip);
    expect(flip).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByTestId("flashcard-back")).toHaveTextContent(
      "Mass is the amount of matter.",
    );
  });

  it("placeholder card (failed AI answer) can be filled in", async () => {
    const placeholder = item({
      flashcard: {
        ...item().flashcard!,
        back_text: "",
        back_is_placeholder: true,
      },
    });
    listMine.mockResolvedValue(pageOf([placeholder]));
    updateBack.mockResolvedValue({
      ...placeholder.flashcard!,
      back_text: "My answer",
    });
    renderClient();
    fireEvent.click(await screen.findByTestId("flashcard-flip"));
    expect(screen.getByTestId("flashcard-placeholder")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("flashcard-edit"));

    // Empty submit is rejected by the zod schema — no request sent.
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(
      await screen.findByText("Write an answer before saving."),
    ).toBeInTheDocument();
    expect(updateBack).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText(/Answer on the back of the card/), {
      target: { value: "My answer" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() =>
      expect(updateBack).toHaveBeenCalledWith("tok", "fc-1", {
        back_text: "My answer",
      }),
    );
  });

  it("delete asks for confirmation then deletes", async () => {
    listMine.mockResolvedValue(pageOf([item()]));
    deleteHighlight.mockResolvedValue({ deleted: true });
    renderClient();
    fireEvent.click(await screen.findByTestId("my-highlight-delete"));
    expect(deleteHighlight).not.toHaveBeenCalled();
    fireEvent.click(screen.getByTestId("my-highlight-delete-confirm"));
    await waitFor(() =>
      expect(deleteHighlight).toHaveBeenCalledWith("tok", "h-1"),
    );
  });

  it("surfaces a mutation error", async () => {
    listMine.mockResolvedValue(pageOf([item()]));
    deleteHighlight.mockRejectedValueOnce(new Error("nope"));
    renderClient();
    fireEvent.click(await screen.findByTestId("my-highlight-delete"));
    fireEvent.click(screen.getByTestId("my-highlight-delete-confirm"));
    expect(
      await screen.findByText("That didn't work. Please try again."),
    ).toBeInTheDocument();
  });

  it("paginates", async () => {
    listMine.mockImplementation((_t: string, page: number) =>
      Promise.resolve(pageOf([item({ id: `h-${page}` })], 2, page)),
    );
    renderClient();
    await screen.findByText("Page 1 of 2");
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() =>
      expect(listMine).toHaveBeenLastCalledWith("tok", 2, 20),
    );
  });

  it("renders in Urdu (RTL locale) via translation keys", async () => {
    listMine.mockResolvedValue(pageOf([]));
    renderClient("ur");
    expect(
      await screen.findByText("ابھی کوئی نمایاں عبارت نہیں"),
    ).toBeInTheDocument();
  });

  it("lecturePositionHref encodes the highlight id", () => {
    expect(lecturePositionHref(item({ id: "a b" }))).toBe(
      "/student/lectures/lec-1?highlight=a%20b",
    );
  });
});
