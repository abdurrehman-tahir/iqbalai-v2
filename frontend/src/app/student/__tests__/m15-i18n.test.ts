/**
 * T-193 — every M-15 string exists in en/ur/sd/ps with real translations
 * (no __TODO__, no empty values, identical key sets, ICU placeholders kept).
 */
import { describe, expect, it } from "vitest";
import en from "../../../../messages/en/common.json";
import ur from "../../../../messages/ur/common.json";
import sd from "../../../../messages/sd/common.json";
import ps from "../../../../messages/ps/common.json";

type Tree = { [k: string]: string | Tree };

const LOCALES: Record<string, Tree> = { en, ur, sd, ps } as unknown as Record<
  string,
  Tree
>;

// Every namespace M-15 added (plus the one viewer key it added to M-12's).
const M15_NAMESPACES = [
  "student.nav",
  "student.highlights",
  "student.enrichment",
  "student.lecture_rating",
  "teacher.lecture_quality",
];
const M15_SINGLE_KEYS = ["student.lecture_viewer.highlight_mark_label"];

function at(tree: Tree, path: string): string | Tree | undefined {
  return path
    .split(".")
    .reduce<string | Tree | undefined>(
      (node, key) => (node && typeof node === "object" ? node[key] : undefined),
      tree,
    );
}

function flatten(
  node: string | Tree | undefined,
  prefix: string,
  out: Map<string, string>,
) {
  if (typeof node === "string") {
    out.set(prefix, node);
    return out;
  }
  for (const [k, v] of Object.entries(node ?? {}))
    flatten(v, `${prefix}.${k}`, out);
  return out;
}

function m15Strings(locale: Tree): Map<string, string> {
  const out = new Map<string, string>();
  for (const ns of M15_NAMESPACES) flatten(at(locale, ns), ns, out);
  for (const key of M15_SINGLE_KEYS) flatten(at(locale, key), key, out);
  return out;
}

function placeholders(value: string): string[] {
  // Top-level ICU arguments: {name} and {count, plural, ...}
  return [...value.matchAll(/\{(\w+)[,}]/g)].map((m) => m[1]).sort();
}

describe("M-15 i18n completeness (en/ur/sd/ps)", () => {
  const english = m15Strings(LOCALES.en);

  it("has M-15 strings at all", () => {
    expect(english.size).toBeGreaterThan(60);
  });

  for (const locale of ["ur", "sd", "ps"]) {
    it(`${locale}: same keys, no __TODO__, no empty values, placeholders preserved`, () => {
      const strings = m15Strings(LOCALES[locale]);
      expect([...strings.keys()].sort()).toEqual([...english.keys()].sort());
      for (const [key, value] of strings) {
        expect(value, key).not.toMatch(/__TODO__/);
        expect(value.trim(), key).not.toBe("");
        expect(placeholders(value), key).toEqual(
          placeholders(english.get(key)!),
        );
      }
    });

    it(`${locale}: is actually translated (not copied English)`, () => {
      const strings = m15Strings(LOCALES[locale]);
      // Format-only strings ("{score} / 100", "{name} · {sector}") are legitimately
      // identical — only flag English *words* outside ICU placeholders.
      const words = (value: string) =>
        value.replace(/\{[^{}]*(\{[^{}]*\}[^{}]*)*\}/g, "");
      const copied = [...strings].filter(
        ([key, value]) =>
          value === english.get(key) && /[A-Za-z]{4,}/.test(words(value)),
      );
      expect(copied.map(([k]) => k)).toEqual([]);
    });
  }
});
