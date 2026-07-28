import { DiagnosticTakingClient } from "./DiagnosticTakingClient";

const DEMO_QUESTIONS = [
  {
    id: "q1",
    prompt: "Which quantity is a force?",
    choices: ["Mass", "Newton", "Second", "Meter"],
    topic: "Newton's Laws",
  },
  {
    id: "q2",
    prompt: "Light bending in a lens relates to…",
    choices: ["Reflection", "Refraction", "Diffraction", "Conduction"],
    topic: "Optics",
  },
  {
    id: "q3",
    prompt: "Describe one everyday example of friction.",
    choices: [],
    topic: "Friction",
  },
];

export default function StudentDiagnosticsPage() {
  return (
    <DiagnosticTakingClient
      startRequest={{
        subject_id: "demo-subject",
        subject_name: "Physics",
        grade_label: "Grade 9",
        framework_name: "",
        generate: false,
        question_count: 15,
        language: "en",
        context_json: {},
        questions: DEMO_QUESTIONS,
      }}
    />
  );
}
