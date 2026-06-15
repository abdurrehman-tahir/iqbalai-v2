/**
 * Minimal next-intl mock for unit tests.
 * useTranslations returns a function that echoes the key (or a provided override).
 */
import { vi } from "vitest";

export const useTranslations = vi.fn(() => (key: string, params?: Record<string, unknown>) => {
  if (params) {
    return Object.entries(params).reduce(
      (s, [k, v]) => s.replace(`{${k}}`, String(v)),
      key,
    );
  }
  return key;
});

export const useFormatter = vi.fn(() => ({
  dateTime: (date: Date) => date.toISOString().slice(0, 10),
}));

export const useLocale = vi.fn(() => "en");
