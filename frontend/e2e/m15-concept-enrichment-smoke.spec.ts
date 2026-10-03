/**
 * T-191 — concept enrichment + mini-sim acceptance path (@smoke @mock).
 * The backend is route-mocked (LLM never reached): first request is a cache
 * miss (pending), the next is ready; sim state round-trips through PUT/GET.
 */
import { expect, test, type Page } from "@playwright/test";
import { installStudentMocks } from "./helpers/m15-mocks";

const CONCEPT = {
  concept_id: "physics/forces",
  label: "forces",
  first_paragraph_id: "p1",
  first_paragraph_ordinal: 0,
};

const READY = {
  concept_id: "physics/forces",
  concept_label: "forces",
  status: "ready",
  real_world_uses: [
    { title: "Rickshaws", description: "Heavier loads need more force." },
    { title: "Cricket", description: "A bat changes the ball's momentum." },
  ],
  careers: [{ id: "c1", name: "Civil Engineer", sector: "Engineering" }],
  mini_sim: {
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
  },
  generated_at: "2026-10-03T12:00:00Z",
  refreshing: false,
};

async function mockEnrichment(
  page: Page,
  saved: { values: Record<string, number> },
) {
  let enrichmentCalls = 0;
  await installStudentMocks(page, ({ method, path, body }) => {
    if (method === "GET" && path === "/students/me/lectures/lec-m15/concepts")
      return [CONCEPT];
    if (
      method === "GET" &&
      path === "/students/me/lectures/lec-m15/enrichment"
    ) {
      enrichmentCalls += 1;
      // Cache miss on first reach → pending; generation then lands.
      return enrichmentCalls === 1
        ? {
            ...READY,
            status: "pending",
            real_world_uses: [],
            careers: [],
            mini_sim: null,
          }
        : READY;
    }
    if (path === "/students/me/lectures/lec-m15/simulation") {
      if (method === "PUT") {
        saved.values = (body as { values: Record<string, number> }).values;
      }
      return {
        concept_id: "physics/forces",
        values: saved.values,
        was_reset: false,
      };
    }
    return undefined;
  });
}

test.describe("M-15 concept enrichment + mini-sim @smoke @mock", () => {
  test("reaching a concept shows uses, careers and a sim whose state persists", async ({
    page,
  }) => {
    const saved = { values: {} as Record<string, number> };
    await mockEnrichment(page, saved);

    await page.goto("/student/lectures/lec-m15");
    const card = page.getByTestId("concept-enrichment");
    await expect(card).toBeVisible({ timeout: 15_000 });
    await expect(card.getByTestId("concept-uses")).toContainText("Rickshaws", {
      timeout: 15_000,
    });
    await expect(card.getByTestId("concept-careers")).toContainText(
      "Civil Engineer",
    );
    await expect(card.getByTestId("mini-sim-output")).toHaveText("Force: 20 N");

    await card.getByTestId("mini-sim-slider-mass").fill("40");
    await expect(card.getByTestId("mini-sim-output")).toHaveText("Force: 80 N");
    await expect.poll(() => saved.values.mass, { timeout: 5_000 }).toBe(40);

    await page.reload();
    await expect(page.getByTestId("mini-sim-output")).toHaveText(
      "Force: 80 N",
      {
        timeout: 15_000,
      },
    );
    await expect(page.getByTestId("mini-sim-slider-mass")).toHaveValue("40");
  });

  test("RTL (Urdu) at 360px: card renders right-to-left inside the viewport", async ({
    page,
    context,
  }) => {
    await context.addCookies([
      { name: "locale", value: "ur", url: "http://localhost:3100" },
    ]);
    await page.setViewportSize({ width: 360, height: 740 });
    await mockEnrichment(page, { values: {} });

    await page.goto("/student/lectures/lec-m15");
    await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
    const card = page.getByTestId("concept-enrichment");
    await expect(card.getByTestId("concept-uses")).toBeVisible({
      timeout: 15_000,
    });
    await expect(card).toContainText("حقیقی زندگی میں");
    // The card itself must fit the 360px floor. (Whole-page overflow is not
    // asserted here: pre-existing untranslated student-shell keys in ur/sd/ps —
    // outside M-15 — widen the mode switcher; see the M-15 PR known issues.)
    const box = await card.boundingBox();
    expect(box).not.toBeNull();
    expect(box!.x).toBeGreaterThanOrEqual(0);
    expect(box!.x + box!.width).toBeLessThanOrEqual(360);
    const slider = card.getByTestId("mini-sim-slider-mass");
    const sliderBox = await slider.boundingBox();
    expect(sliderBox!.height).toBeGreaterThanOrEqual(44); // touch target
  });
});
