import type { ReviewClusterView, ReviewDetailRead, ReviewSummaryRead } from "@/lib/api";

export const SUMMARY: ReviewSummaryRead = {
  id: "rev-1",
  lecture_id: "lec-1",
  lecture_title: "Newton's Laws",
  offering_label: "Grade 9 Physics",
  review_date: "2026-10-22",
  generated_at: "2026-10-22T23:30:00Z",
  status: "pending",
  pending_action: true,
  dismissed_at: null,
  acted_actions: [],
  critical_count: 1,
  high_frequency_count: 1,
  read_only: false,
};

export function cluster(
  ref: string,
  column: ReviewClusterView["column"],
  overrides: Partial<ReviewClusterView> = {},
): ReviewClusterView {
  return {
    cluster_ref: ref,
    lecture_id: "lec-1",
    column,
    question_count: 3,
    unique_student_count: 3,
    criticality: column === "critical" ? 8 : 3,
    representative_question: `Why ${ref}?`,
    mini_lecture_id: null,
    skipped: false,
    questions: [
      {
        question_id: `${ref}-q0`,
        question_text: `Why ${ref}? (Ali)`,
        student_user_id: "stu-0",
        student_name: "Ali",
        paragraph_id: "p1",
        source_chunk_id: "c1",
        occurred_at: "2026-10-22T10:00:00Z",
      },
    ],
    ...overrides,
  };
}

export const DETAIL: ReviewDetailRead = {
  ...SUMMARY,
  ai_summary: "Students mixed up action and reaction forces.",
  reflective_prompt: "Would a worked example with everyday objects help?",
  reflected: false,
  mini_lecture_id: "mini-1",
  mini_preview: "Force pairs act on different bodies…",
  mini_published: false,
  critical: [cluster("a", "critical")],
  high_frequency: [cluster("b", "high_frequency")],
  replies: [],
  is_owner: true,
  can_act: true,
};
