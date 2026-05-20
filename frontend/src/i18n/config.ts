export const locales = ["en", "ur", "sd", "ps"] as const;
export type Locale = (typeof locales)[number];
export const defaultLocale: Locale = "en";

export const rtlLocales: Locale[] = ["ur", "sd", "ps"];

export function isRtl(locale: Locale): boolean {
  return rtlLocales.includes(locale);
}
