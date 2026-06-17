/**
 * Payloads the admin UI sends after Phase 2 contract alignment.
 * Mirrored from SyllabiClient / SubscriptionTiersClient submit handlers.
 */

/** SyllabiClient createMutation → syllabiApi.create */
export const EXAM_SYLLABUS_CREATE_FROM_UI = {
  name: "Matric Punjab Board",
  exam_board: "Punjab Board",
  language: "en",
} as const;

/** SubscriptionTiersClient createMutation → subscriptionsApi.create */
export const SUBSCRIPTION_TIER_CREATE_FROM_UI = {
  name: "School Basic",
  slug: "school-basic",
  applies_to: "school" as const,
  pricing_monthly_pkr: 5000,
  caps: {},
} as const;

/** SubjectsClient createMutation → subjectsApi.create (T-041) */
export const SUBJECT_CREATE_FROM_UI = {
  name: "Physics",
  language: "en",
} as const;
