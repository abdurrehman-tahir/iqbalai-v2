import { describe, expect, expectTypeOf, it } from "vitest";

import type { ExamSyllabusCreate, LibraryBookRead } from "@/lib/api/types";

/**
 * T-224 — type-level guard for the generated API client.
 *
 * If `pnpm gen:api` ever breaks (or the re-export wiring rots), these fail to
 * compile under tsc, so they protect the generation path itself rather than any
 * runtime behaviour.
 */
describe("generated API types", () => {
  it("ExamSyllabusCreate carries the expected request fields", () => {
    const payload: ExamSyllabusCreate = {
      exam_board: "FBISE",
      name: "Matriculation",
      language: "en",
    };
    expectTypeOf(payload.name).toEqualTypeOf<string>();
    expectTypeOf(payload.exam_board).toEqualTypeOf<string>();
    expect(payload.name).toBe("Matriculation");
  });

  it("LibraryBookRead exposes id + status from the backend schema", () => {
    expectTypeOf<LibraryBookRead>().toHaveProperty("id");
    expectTypeOf<LibraryBookRead>().toHaveProperty("status");
    expectTypeOf<LibraryBookRead["id"]>().toEqualTypeOf<string>();
  });
});
