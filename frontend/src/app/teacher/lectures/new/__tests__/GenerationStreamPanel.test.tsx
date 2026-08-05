/**
 * T-117 — GenerationStreamPanel (wizard Step 5's live-generation view).
 * Exercises all four UI states by mocking `useLectureGenerationStream` directly —
 * the actual WebSocket reconnect/backoff logic is covered by
 * `lecture-generation-socket.test.ts`.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NextIntlClientProvider } from "next-intl";
import en from "../../../../../../messages/en/common.json";
import { LectureWizardClient } from "../LectureWizardClient";
import type { LectureGenerationState } from "@/lib/ws/lecture-generation-socket";
import type { VoiceSessionState, VoiceSessionControls } from "@/lib/ws/lecture-voice-socket";

vi.mock("@/hooks/use-client-auth", () => ({
  useClientAuth: () => ({ mounted: true, token: "tok" }),
}));

const mockStream = vi.fn<() => LectureGenerationState>();
vi.mock("@/lib/ws/lecture-generation-socket", () => ({
  useLectureGenerationStream: () => mockStream(),
}));

const mockVoice = vi.fn<() => VoiceSessionState & VoiceSessionControls>();
vi.mock("@/lib/ws/lecture-voice-socket", () => ({
  useLectureVoiceSession: () => mockVoice(),
}));

const IDLE_VOICE_STATE: VoiceSessionState & VoiceSessionControls = {
  status: "idle",
  turns: [],
  errorReason: null,
  unavailableNotice: null,
  startSession: vi.fn(),
  endSession: vi.fn(),
  startRecording: vi.fn(),
  stopRecording: vi.fn(),
};

const listOfferings = vi.fn();
const listCurricula = vi.fn();
const listTopics = vi.fn();
const listReferences = vi.fn();
const getDraft = vi.fn();
const upsertDraft = vi.fn();
const getEstimate = vi.fn();
const generate = vi.fn();
const getParagraphs = vi.fn();
const listLinks = vi.fn();
const createLink = vi.fn();
const getAccessSettings = vi.fn();
const setAccessSettings = vi.fn();
const getRoster = vi.fn();

vi.mock("@/lib/api", () => ({
  lectureWizardApi: {
    listOfferings: (...args: unknown[]) => listOfferings(...args),
    listCurricula: (...args: unknown[]) => listCurricula(...args),
    listTopics: (...args: unknown[]) => listTopics(...args),
    listReferences: (...args: unknown[]) => listReferences(...args),
    getDraft: (...args: unknown[]) => getDraft(...args),
    upsertDraft: (...args: unknown[]) => upsertDraft(...args),
    getEstimate: (...args: unknown[]) => getEstimate(...args),
    generate: (...args: unknown[]) => generate(...args),
    getParagraphs: (...args: unknown[]) => getParagraphs(...args),
    listLinks: (...args: unknown[]) => listLinks(...args),
    createLink: (...args: unknown[]) => createLink(...args),
    getAccessSettings: (...args: unknown[]) => getAccessSettings(...args),
    setAccessSettings: (...args: unknown[]) => setAccessSettings(...args),
    getRoster: (...args: unknown[]) => getRoster(...args),
  },
  ApiError: class ApiError extends Error {
    constructor(
      public status: number,
      public code: string,
      message: string
    ) {
      super(message);
    }
  },
}));

const DEFAULT_OFFERING = {
  id: "off-1",
  grade_id: "g-1",
  grade_name: "Grade 9",
  grade_level_ordinal: 9,
  subject_id: "s-1",
  subject_name: "Physics",
  academic_session: "2025-2026",
};

function renderAtStep5GeneratingLecture(
  offerings: (typeof DEFAULT_OFFERING)[] = [DEFAULT_OFFERING],
  links: unknown[] = []
) {
  getDraft.mockResolvedValue({
    id: "draft-1",
    teacher_user_id: "t-1",
    step: 5,
    data: {
      grade_subject_offering_id: "off-1",
      topic: "Newton's Laws",
      topic_source: "tree",
      curriculum_id: "curr-1",
      reference_book_ids: [],
      include_cross_grade: false,
      teaching_mode: "auto",
      lecture_id: "lec-1",
    },
    updated_at: "2026-07-30T00:00:00Z",
  });
  listOfferings.mockResolvedValue(offerings);
  listCurricula.mockResolvedValue([]);
  listReferences.mockResolvedValue([]);
  getEstimate.mockResolvedValue({
    estimated_seconds: 60,
    reference_count: 0,
    teaching_mode: "auto",
  });
  listLinks.mockResolvedValue(links);
  getAccessSettings.mockResolvedValue({
    lecture_id: "lec-1",
    is_restricted: false,
    assignments: [],
  });

  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <NextIntlClientProvider locale="en" messages={en}>
        <LectureWizardClient />
      </NextIntlClientProvider>
    </QueryClientProvider>
  );
}

describe("GenerationStreamPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockVoice.mockReturnValue({ ...IDLE_VOICE_STATE });
  });

  it("shows a loading skeleton while connecting with no output yet", async () => {
    mockStream.mockReturnValue({
      status: "connecting",
      text: "",
      versionId: null,
      errorReason: null,
    });
    renderAtStep5GeneratingLecture();

    expect(await screen.findByText(/Generating your lecture/i)).toBeInTheDocument();
    expect(screen.getByText(/Generating your lecture/i).closest("section")).toHaveAttribute(
      "aria-busy",
      "true"
    );
  });

  it("streams live tokens into the transcript", async () => {
    mockStream.mockReturnValue({
      status: "streaming",
      text: "Newton's first law states that...",
      versionId: null,
      errorReason: null,
    });
    renderAtStep5GeneratingLecture();

    expect(
      await screen.findByText(/Newton's first law states that/i)
    ).toBeInTheDocument();
  });

  it("shows a reconnecting notice without losing the transcript so far", async () => {
    mockStream.mockReturnValue({
      status: "reconnecting",
      text: "Newton's first law",
      versionId: null,
      errorReason: null,
    });
    renderAtStep5GeneratingLecture();

    expect(await screen.findByText(/reconnecting/i)).toBeInTheDocument();
    expect(screen.getByText(/Newton's first law/i)).toBeInTheDocument();
  });

  it("shows the ready state and source-badged paragraphs when generation completes", async () => {
    mockStream.mockReturnValue({
      status: "complete",
      text: "Newton's first law states that...",
      versionId: "ver-1",
      errorReason: null,
    });
    getParagraphs.mockResolvedValue([
      { ordinal: 0, text: "Newton's first law...", tier: "curriculum", book_name: null },
      {
        ordinal: 1,
        text: "For example, a bus braking...",
        tier: "reference",
        book_name: "Physics Today",
      },
      { ordinal: 2, text: "This extends to rotation.", tier: "ai_knowledge", book_name: null },
    ]);
    renderAtStep5GeneratingLecture();

    expect(await screen.findByText(/Lecture ready/i)).toBeInTheDocument();
    expect(await screen.findByText("Curriculum")).toBeInTheDocument();
    expect(await screen.findByText("Ref: Physics Today")).toBeInTheDocument();
    expect(await screen.findByText("AI Knowledge")).toBeInTheDocument();
    expect(screen.getByText(/For example, a bus braking/i)).toBeInTheDocument();
  });

  it("shows the Web badge for T-119 out-of-curriculum fallback paragraphs", async () => {
    mockStream.mockReturnValue({
      status: "complete",
      text: "Quantum foam is a concept...",
      versionId: "ver-1",
      errorReason: null,
    });
    getParagraphs.mockResolvedValue([
      { ordinal: 0, text: "Quantum foam is a concept...", tier: "web", book_name: null },
    ]);
    renderAtStep5GeneratingLecture();

    expect(await screen.findByText("Web")).toBeInTheDocument();
  });

  it("shows a paragraphs error state with retry when the read fails", async () => {
    mockStream.mockReturnValue({
      status: "complete",
      text: "Newton's first law...",
      versionId: "ver-1",
      errorReason: null,
    });
    getParagraphs.mockRejectedValue(new Error("network error"));
    renderAtStep5GeneratingLecture();

    expect(
      await screen.findByRole("heading", { name: /Could not load the lecture content/i })
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("shows an error state when generation fails", async () => {
    mockStream.mockReturnValue({
      status: "error",
      text: "",
      versionId: null,
      errorReason: "timed_out",
    });
    renderAtStep5GeneratingLecture();

    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(await screen.findByText(/Generation failed/i)).toBeInTheDocument();
    expect(screen.getByText(/timed out/i)).toBeInTheDocument();
  });
});

describe("VoiceConversationPanel (T-121)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getParagraphs.mockResolvedValue([]);
    mockStream.mockReturnValue({
      status: "complete",
      text: "Newton's first law...",
      versionId: "ver-1",
      errorReason: null,
    });
  });

  it("shows a 'Talk to AI' button when idle", async () => {
    mockVoice.mockReturnValue({ ...IDLE_VOICE_STATE });
    renderAtStep5GeneratingLecture();

    expect(await screen.findByRole("button", { name: /talk to ai/i })).toBeInTheDocument();
  });

  it("starts a session when the Talk to AI button is clicked", async () => {
    const startSession = vi.fn();
    mockVoice.mockReturnValue({ ...IDLE_VOICE_STATE, startSession });
    const user = userEvent.setup();
    renderAtStep5GeneratingLecture();

    await user.click(await screen.findByRole("button", { name: /talk to ai/i }));
    expect(startSession).toHaveBeenCalledTimes(1);
  });

  it("shows a mic button in the ready state and starts recording on click", async () => {
    const startRecording = vi.fn();
    mockVoice.mockReturnValue({
      ...IDLE_VOICE_STATE,
      status: "ready",
      startRecording,
    });
    const user = userEvent.setup();
    renderAtStep5GeneratingLecture();

    const micButton = await screen.findByRole("button", { name: /start recording/i });
    await user.click(micButton);
    expect(startRecording).toHaveBeenCalledTimes(1);
  });

  it("shows a stop button while recording", async () => {
    mockVoice.mockReturnValue({ ...IDLE_VOICE_STATE, status: "recording" });
    renderAtStep5GeneratingLecture();

    expect(await screen.findByRole("button", { name: /stop recording/i })).toBeInTheDocument();
  });

  it("renders the conversation transcript with confirmation text", async () => {
    mockVoice.mockReturnValue({
      ...IDLE_VOICE_STATE,
      status: "ready",
      turns: [
        {
          transcript: "add an example about Newton's third law",
          confirmation: "Adding an example about Newton's third law.",
          hadDraftEdit: true,
        },
      ],
    });
    renderAtStep5GeneratingLecture();

    expect(
      await screen.findByText("add an example about Newton's third law")
    ).toBeInTheDocument();
    expect(
      screen.getByText("Adding an example about Newton's third law.")
    ).toBeInTheDocument();
    expect(screen.getByText(/lecture draft updated/i)).toBeInTheDocument();
  });

  it("shows the TTS-unavailable notice without blocking the conversation", async () => {
    mockVoice.mockReturnValue({
      ...IDLE_VOICE_STATE,
      status: "ready",
      unavailableNotice: "voice not yet available in sd; reading aloud disabled.",
    });
    renderAtStep5GeneratingLecture();

    expect(await screen.findByText(/reading aloud disabled/i)).toBeInTheDocument();
    // The session stays usable — mic button is still there, not replaced by an error.
    expect(screen.getByRole("button", { name: /start recording/i })).toBeInTheDocument();
  });

  it("shows an error state on a voice session error", async () => {
    mockVoice.mockReturnValue({
      ...IDLE_VOICE_STATE,
      status: "error",
      errorReason: "turn_processing_failed",
    });
    renderAtStep5GeneratingLecture();

    expect(await screen.findByText(/voice session error/i)).toBeInTheDocument();
  });

  it("shows an ended message once the session ends", async () => {
    mockVoice.mockReturnValue({ ...IDLE_VOICE_STATE, status: "ended" });
    renderAtStep5GeneratingLecture();

    expect(await screen.findByText(/voice session ended/i)).toBeInTheDocument();
  });
});

describe("LectureLinksPanel (T-122)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockVoice.mockReturnValue({ ...IDLE_VOICE_STATE });
    getParagraphs.mockResolvedValue([]);
    mockStream.mockReturnValue({
      status: "complete",
      text: "Newton's first law...",
      versionId: "ver-1",
      errorReason: null,
    });
  });

  // A second offering the teacher owns, at a lower grade — a valid link target.
  const TWO_OFFERINGS = [
    DEFAULT_OFFERING,
    {
      id: "off-2",
      grade_id: "g-2",
      grade_name: "Grade 8",
      grade_level_ordinal: 8,
      subject_id: "s-2",
      subject_name: "Chemistry",
      academic_session: "2025-2026",
    },
  ];

  it("shows an empty state when the lecture has no links yet", async () => {
    renderAtStep5GeneratingLecture(TWO_OFFERINGS, []);

    expect(await screen.findByText(/not linked to any other/i)).toBeInTheDocument();
  });

  it("renders existing links", async () => {
    renderAtStep5GeneratingLecture(TWO_OFFERINGS, [
      {
        id: "link-1",
        lecture_id: "lec-1",
        target_grade_subject_offering_id: "off-2",
        target_grade_id: "g-2",
        target_grade_name: "Grade 8",
        target_grade_level_ordinal: 8,
        target_subject_id: "s-2",
        target_subject_name: "Chemistry",
        created_at: "2026-08-05T00:00:00Z",
      },
    ]);

    const list = await screen.findByRole("list");
    expect(within(list).getByText(/grade 8/i)).toBeInTheDocument();
    expect(within(list).getByText(/chemistry/i)).toBeInTheDocument();
  });

  it("links the lecture into another owned offering", async () => {
    listLinks.mockResolvedValueOnce([]).mockResolvedValueOnce([
      {
        id: "link-1",
        lecture_id: "lec-1",
        target_grade_subject_offering_id: "off-2",
        target_grade_id: "g-2",
        target_grade_name: "Grade 8",
        target_grade_level_ordinal: 8,
        target_subject_id: "s-2",
        target_subject_name: "Chemistry",
        created_at: "2026-08-05T00:00:00Z",
      },
    ]);
    createLink.mockResolvedValue({
      id: "link-1",
      lecture_id: "lec-1",
      target_grade_subject_offering_id: "off-2",
      target_grade_id: "g-2",
      target_grade_name: "Grade 8",
      target_grade_level_ordinal: 8,
      target_subject_id: "s-2",
      target_subject_name: "Chemistry",
      created_at: "2026-08-05T00:00:00Z",
    });
    const user = userEvent.setup();
    renderAtStep5GeneratingLecture(TWO_OFFERINGS);

    await screen.findByText(/not linked to any other/i);
    await user.selectOptions(screen.getByLabelText(/link into another offering/i), "off-2");
    await user.click(screen.getByRole("button", { name: /link lecture/i }));

    expect(createLink).toHaveBeenCalledWith("tok", "lec-1", {
      target_grade_subject_offering_id: "off-2",
    });
    const list = await screen.findByRole("list");
    expect(within(list).getByText(/grade 8/i)).toBeInTheDocument();
  });

  it("shows an inline error when linking fails", async () => {
    createLink.mockRejectedValue(new Error("PRECONDITION_FAILED"));
    const user = userEvent.setup();
    renderAtStep5GeneratingLecture(TWO_OFFERINGS, []);

    await user.selectOptions(await screen.findByLabelText(/link into another offering/i), "off-2");
    await user.click(screen.getByRole("button", { name: /link lecture/i }));

    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });

  it("shows an error state with retry when the links read fails", async () => {
    renderAtStep5GeneratingLecture(TWO_OFFERINGS);
    // Set after render: the helper's own default listLinks resolution must not
    // stomp this rejection (queryFn execution is deferred past the sync render).
    listLinks.mockRejectedValue(new Error("network error"));

    expect(await screen.findByRole("button", { name: /retry/i })).toBeInTheDocument();
  });
});

describe("LectureAccessPanel (T-123)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockVoice.mockReturnValue({ ...IDLE_VOICE_STATE });
    getParagraphs.mockResolvedValue([]);
    listLinks.mockResolvedValue([]);
    mockStream.mockReturnValue({
      status: "complete",
      text: "Newton's first law...",
      versionId: "ver-1",
      errorReason: null,
    });
    getRoster.mockResolvedValue({
      sections: [
        { id: "section-a", name: "A" },
        { id: "section-b", name: "B" },
      ],
      students: [
        { id: "student-1", display_name: "Student One", section_id: "section-a" },
        { id: "student-2", display_name: "Student Two", section_id: "section-b" },
      ],
    });
  });

  it("shows the unrestricted summary by default", async () => {
    getAccessSettings.mockResolvedValue({
      lecture_id: "lec-1",
      is_restricted: false,
      assignments: [],
    });
    renderAtStep5GeneratingLecture();

    expect(await screen.findByText(/visible to all students enrolled/i)).toBeInTheDocument();
  });

  it("shows the restricted summary with the assignment list", async () => {
    renderAtStep5GeneratingLecture();
    // Set after render: the helper's own default getAccessSettings resolution
    // must not stomp this override (queryFn execution is deferred past render).
    getAccessSettings.mockResolvedValue({
      lecture_id: "lec-1",
      is_restricted: true,
      assignments: [
        {
          id: "assign-1",
          scope: "student",
          student_user_id: "student-1",
          student_name: "Student One",
          section_id: null,
          section_name: null,
          created_at: "2026-08-05T00:00:00Z",
        },
      ],
    });

    expect(await screen.findByText(/restricted to 1 selection/i)).toBeInTheDocument();
    expect(screen.getByText("Student One")).toBeInTheDocument();
  });

  it("lets the teacher restrict access to a section", async () => {
    getAccessSettings
      .mockResolvedValueOnce({ lecture_id: "lec-1", is_restricted: false, assignments: [] })
      .mockResolvedValueOnce({
        lecture_id: "lec-1",
        is_restricted: true,
        assignments: [
          {
            id: "assign-1",
            scope: "section",
            student_user_id: null,
            student_name: null,
            section_id: "section-a",
            section_name: "A",
            created_at: "2026-08-05T00:00:00Z",
          },
        ],
      });
    setAccessSettings.mockResolvedValue({
      lecture_id: "lec-1",
      is_restricted: true,
      assignments: [
        {
          id: "assign-1",
          scope: "section",
          student_user_id: null,
          student_name: null,
          section_id: "section-a",
          section_name: "A",
          created_at: "2026-08-05T00:00:00Z",
        },
      ],
    });
    const user = userEvent.setup();
    renderAtStep5GeneratingLecture();

    await user.click(await screen.findByRole("button", { name: /edit access/i }));
    const sectionACheckbox = await screen.findByRole("checkbox", { name: "A" });
    await user.click(sectionACheckbox);
    await user.click(screen.getByRole("button", { name: /save access settings/i }));

    expect(setAccessSettings).toHaveBeenCalledWith("tok", "lec-1", {
      assignments: [{ scope: "section", section_id: "section-a" }],
    });
    expect(await screen.findByText(/restricted to 1 selection/i)).toBeInTheDocument();
  });

  it("lets the teacher cancel editing without saving", async () => {
    getAccessSettings.mockResolvedValue({
      lecture_id: "lec-1",
      is_restricted: false,
      assignments: [],
    });
    const user = userEvent.setup();
    renderAtStep5GeneratingLecture();

    await user.click(await screen.findByRole("button", { name: /edit access/i }));
    await screen.findByRole("checkbox", { name: "A" });
    await user.click(screen.getByRole("button", { name: /cancel/i }));

    expect(await screen.findByText(/visible to all students enrolled/i)).toBeInTheDocument();
    expect(setAccessSettings).not.toHaveBeenCalled();
  });

  it("shows an inline error when saving access settings fails", async () => {
    getAccessSettings.mockResolvedValue({
      lecture_id: "lec-1",
      is_restricted: false,
      assignments: [],
    });
    setAccessSettings.mockRejectedValue(new Error("VALIDATION_ERROR"));
    const user = userEvent.setup();
    renderAtStep5GeneratingLecture();

    await user.click(await screen.findByRole("button", { name: /edit access/i }));
    await user.click(await screen.findByRole("button", { name: /save access settings/i }));

    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });

  it("shows an error state with retry when settings fail to load", async () => {
    renderAtStep5GeneratingLecture();
    // Set after render: the helper's own default getAccessSettings resolution
    // must not stomp this rejection (queryFn execution is deferred past render).
    getAccessSettings.mockRejectedValue(new Error("network error"));

    expect(await screen.findByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("shows an error state with retry when the roster fails to load", async () => {
    getAccessSettings.mockResolvedValue({
      lecture_id: "lec-1",
      is_restricted: false,
      assignments: [],
    });
    getRoster.mockRejectedValue(new Error("network error"));
    const user = userEvent.setup();
    renderAtStep5GeneratingLecture();

    await user.click(await screen.findByRole("button", { name: /edit access/i }));

    expect(await screen.findByRole("button", { name: /retry/i })).toBeInTheDocument();
  });
});
