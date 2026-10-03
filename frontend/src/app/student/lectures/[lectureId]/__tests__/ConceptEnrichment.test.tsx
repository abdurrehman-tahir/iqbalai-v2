/** T-190/T-191 — concept enrichment card + mini-simulation (four states, save/restore). */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NextIntlClientProvider } from "next-intl";
import type {
  ConceptEnrichmentRead,
  LectureConceptRead,
  MiniSimSpecRead,
} from "@/lib/api";
import enMessages from "../../../../../../messages/en/common.json";
import urMessages from "../../../../../../messages/ur/common.json";
import {
  ConceptEnrichmentCard,
  ENRICHMENT_POLL_MS,
} from "../ConceptEnrichmentCard";
import { SIM_SAVE_DEBOUNCE_MS } from "../MiniSimulation";
import { evaluateExpression, ExpressionError } from "../mini-sim-expression";

const getEnrichment = vi.fn();
const getSimulation = vi.fn();
const saveSimulation = vi.fn();

vi.mock("@/lib/api", () => ({
  conceptEnrichmentApi: {
    getEnrichment: (...a: unknown[]) => getEnrichment(...a),
    getSimulation: (...a: unknown[]) => getSimulation(...a),
    saveSimulation: (...a: unknown[]) => saveSimulation(...a),
  },
}));
vi.mock("@/hooks/use-client-auth", () => ({
  useClientAuth: () => ({ mounted: true, token: "tok" }),
}));

const CONCEPT: LectureConceptRead = {
  concept_id: "physics/forces",
  label: "forces",
  first_paragraph_id: "p1",
  first_paragraph_ordinal: 0,
};

const SPEC: MiniSimSpecRead = {
  title: "Push the cart",
  scenario: "A cart on a road in Lahore.",
  variables: [
    {
      key: "mass",
      label: "Mass",
      unit: "kg",
      min: 1,
      max: 100,
      step: 1,
      default: 10,
    },
    {
      key: "accel",
      label: "Acceleration",
      unit: "m/s²",
      min: 0,
      max: 10,
      step: 1,
      default: 2,
    },
  ],
  output: { label: "Force", unit: "N", expression: "mass * accel" },
};

function ready(
  overrides: Partial<ConceptEnrichmentRead> = {},
): ConceptEnrichmentRead {
  return {
    concept_id: CONCEPT.concept_id,
    concept_label: "forces",
    status: "ready",
    real_world_uses: [
      { title: "Rickshaws", description: "Heavier loads need more force." },
      { title: "Cricket", description: "A bat changes the ball's momentum." },
    ],
    careers: [{ id: "c1", name: "Civil Engineer", sector: "Engineering" }],
    mini_sim: SPEC,
    generated_at: "2026-10-03T12:00:00Z",
    refreshing: false,
    ...overrides,
  };
}

function renderCard(locale: "en" | "ur" = "en") {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <NextIntlClientProvider
        locale={locale}
        messages={locale === "en" ? enMessages : urMessages}
      >
        <ConceptEnrichmentCard lectureId="lec-1" concept={CONCEPT} />
      </NextIntlClientProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  getEnrichment.mockReset();
  getSimulation.mockReset();
  saveSimulation.mockReset();
  getSimulation.mockResolvedValue({
    concept_id: CONCEPT.concept_id,
    values: {},
    was_reset: false,
  });
  saveSimulation.mockImplementation(
    (_t, _l, _c, body: { values: Record<string, number> }) =>
      Promise.resolve({
        concept_id: CONCEPT.concept_id,
        values: body.values,
        was_reset: false,
      }),
  );
});

afterEach(() => vi.useRealTimers());

describe("mini-sim expression (parity with sim_expression.py)", () => {
  it.each([
    ["mass * acceleration", { mass: 10, acceleration: 2 }, 20],
    ["a + b * c", { a: 1, b: 2, c: 3 }, 7],
    ["(a + b) * c", { a: 1, b: 2, c: 3 }, 9],
    ["2 ^ 3 ^ 2", {}, 512],
    ["-a + 4", { a: 1 }, 3],
    ["0.5 * m * v ^ 2", { m: 2, v: 3 }, 9],
  ])("%s", (expr, values, expected) => {
    expect(evaluateExpression(expr, values)).toBeCloseTo(expected);
  });

  it.each([
    "__import__('os')",
    "a.__class__",
    "alert(1)",
    "a ** b",
    "a; b",
    "a +",
    "(a",
    "x * 2",
    "",
  ])("rejects %s", (expr) => {
    expect(() => evaluateExpression(expr, { a: 1, b: 2 })).toThrow(
      ExpressionError,
    );
  });

  it("division by zero is undefined (null), not an error", () => {
    expect(evaluateExpression("a / b", { a: 1, b: 0 })).toBeNull();
  });
});

describe("ConceptEnrichmentCard — four UI states", () => {
  it("pending (cache miss) shows preparing and polls until ready", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    getEnrichment
      .mockResolvedValueOnce(
        ready({
          status: "pending",
          real_world_uses: [],
          careers: [],
          mini_sim: null,
        }),
      )
      .mockResolvedValue(ready());
    renderCard();
    expect(
      await screen.findByTestId("concept-enrichment-pending"),
    ).toBeInTheDocument();
    await act(async () => {
      vi.advanceTimersByTime(ENRICHMENT_POLL_MS + 50);
    });
    expect(await screen.findByTestId("concept-uses")).toBeInTheDocument();
    expect(getEnrichment).toHaveBeenCalledTimes(2);
    expect(getEnrichment).toHaveBeenCalledWith(
      "tok",
      "lec-1",
      "physics/forces",
    );
  });

  it("failed generation shows an error with retry", async () => {
    getEnrichment
      .mockResolvedValueOnce(ready({ status: "failed" }))
      .mockResolvedValue(ready());
    renderCard();
    expect(
      await screen.findByTestId("concept-enrichment-error"),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByTestId("concept-uses")).toBeInTheDocument();
  });

  it("empty content shows an explanatory message", async () => {
    getEnrichment.mockResolvedValue(
      ready({ real_world_uses: [], careers: [], mini_sim: null }),
    );
    renderCard();
    expect(
      await screen.findByTestId("concept-enrichment-empty"),
    ).toBeInTheDocument();
  });

  it("ready: uses, Pakistani careers and the mini-sim", async () => {
    getEnrichment.mockResolvedValue(ready());
    renderCard();
    expect(
      await screen.findByRole("heading", { name: "Why forces matters" }),
    ).toBeInTheDocument();
    expect(await screen.findByText("Rickshaws")).toBeInTheDocument();
    expect(screen.getByTestId("concept-careers")).toHaveTextContent(
      "Civil Engineer · Engineering",
    );
    expect(await screen.findByTestId("mini-sim-output")).toHaveTextContent(
      "Force: 20 N",
    );
  });

  it("no sim spec → text-only fallback (flow-6 §5.9)", async () => {
    getEnrichment.mockResolvedValue(ready({ mini_sim: null }));
    renderCard();
    expect(await screen.findByTestId("mini-sim-text-only")).toBeInTheDocument();
  });

  it("stale entry shows the updating badge", async () => {
    getEnrichment.mockResolvedValue(ready({ refreshing: true }));
    renderCard();
    expect(
      await screen.findByTestId("concept-enrichment-updating"),
    ).toHaveTextContent("Updating");
  });

  it("renders Urdu strings (RTL locale)", async () => {
    getEnrichment.mockResolvedValue(ready());
    renderCard("ur");
    expect(await screen.findByText("حقیقی زندگی میں")).toBeInTheDocument();
  });
});

describe("MiniSimulation — per-student state", () => {
  it("restores saved values on return", async () => {
    getEnrichment.mockResolvedValue(ready());
    getSimulation.mockResolvedValue({
      concept_id: CONCEPT.concept_id,
      values: { mass: 40, accel: 5 },
      was_reset: false,
    });
    renderCard();
    await waitFor(() =>
      expect(screen.getByTestId("mini-sim-output")).toHaveTextContent(
        "Force: 200 N",
      ),
    );
    expect(screen.getByTestId("mini-sim-slider-mass")).toHaveValue("40");
  });

  it("slider changes recompute output and save (debounced)", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    getEnrichment.mockResolvedValue(ready());
    renderCard();
    const slider = await screen.findByTestId("mini-sim-slider-mass");
    fireEvent.change(slider, { target: { value: "30" } });
    fireEvent.change(slider, { target: { value: "50" } });
    expect(screen.getByTestId("mini-sim-output")).toHaveTextContent(
      "Force: 100 N",
    );
    expect(saveSimulation).not.toHaveBeenCalled();
    await act(async () => {
      vi.advanceTimersByTime(SIM_SAVE_DEBOUNCE_MS + 50);
    });
    await waitFor(() => expect(saveSimulation).toHaveBeenCalledTimes(1));
    expect(saveSimulation).toHaveBeenCalledWith(
      "tok",
      "lec-1",
      "physics/forces",
      {
        values: { mass: 50, accel: 2 },
      },
    );
  });

  it("shows the reset notice when stored state was corrupted", async () => {
    getEnrichment.mockResolvedValue(ready());
    getSimulation.mockResolvedValue({
      concept_id: CONCEPT.concept_id,
      values: {},
      was_reset: true,
    });
    renderCard();
    expect(await screen.findByTestId("mini-sim-reset")).toHaveTextContent(
      "Your progress was reset due to a data issue.",
    );
  });

  it("each slider has an accessible label", async () => {
    getEnrichment.mockResolvedValue(ready());
    renderCard();
    expect(
      await screen.findByRole("slider", { name: /Mass/ }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("slider", { name: /Acceleration/ }),
    ).toBeInTheDocument();
  });
});
