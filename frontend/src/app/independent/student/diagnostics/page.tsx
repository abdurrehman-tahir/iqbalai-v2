import { DiagnosticTakingClient } from "@/app/student/diagnostics/DiagnosticTakingClient";

const DEMO_QUESTIONS = [
  {
    id: "q1",
    prompt: "Which topic is heavily tested in past papers?",
    choices: ["Optics", "Unrelated trivia", "None", "Guessing"],
    topic: "Optics",
  },
  {
    id: "q2",
    prompt: "A high priority_weight topic should get more study time.",
    choices: ["True", "False"],
    topic: "Study planning",
  },
];

export default function IndependentStudentDiagnosticsPage() {
  return (
    <DiagnosticTakingClient
      startRequest={{
        framework_id: "demo-framework",
        framework_name: "Matric Punjab Board",
        subject_name: "",
        grade_label: "",
        generate: false,
        question_count: 15,
        language: "en",
        context_json: {},
        questions: DEMO_QUESTIONS,
      }}
    />
  );
}
