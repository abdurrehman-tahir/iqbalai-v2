"use client";

import { useLocale, useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  studentLecturesApi,
  studentQuestionsApi,
  type LectureAudioAlignmentSpan,
  type LectureAudioCacheRead,
  type StudentLectureParagraphRead,
  type StudentLectureSourceTier,
  type StudentQuestionRead,
} from "@/lib/api";
import { useClientAuth } from "@/hooks/use-client-auth";
import { KaraokePlayer } from "./KaraokePlayer";
import {
  HighlightQuestionBox,
  type HighlightSelection,
} from "./HighlightQuestionBox";
import { AnswerSidePanel } from "./AnswerSidePanel";
import { QuestionsTab } from "./QuestionsTab";
import { TeacherShareToggle } from "./TeacherShareToggle";

type Props = { lectureId: string };

const TIER_KEY: Record<StudentLectureSourceTier, string> = {
  curriculum: "badge_curriculum",
  reference: "badge_reference",
  ai_knowledge: "badge_ai",
  web: "badge_web",
};

function SourceBadge({
  paragraph,
  t,
}: {
  paragraph: StudentLectureParagraphRead;
  t: ReturnType<typeof useTranslations>;
}) {
  const label =
    paragraph.tier === "reference" && paragraph.book_name
      ? t("badge_reference_named", { book: paragraph.book_name })
      : t(TIER_KEY[paragraph.tier] ?? "badge_none");
  return (
    <span
      className="inline-flex items-center rounded border border-gray-200 bg-gray-50 px-1.5 py-0.5 text-[11px] font-medium text-gray-600"
      data-testid="source-badge"
      data-tier={paragraph.tier}
    >
      {label}
    </span>
  );
}

function localeToTtsLang(locale: string): "en" | "ur" | "sd" | "ps" {
  if (locale === "ur" || locale === "sd" || locale === "ps") return locale;
  return "en";
}

async function readSseAnswer(url: string, onChunk: (text: string) => void): Promise<string> {
  const res = await fetch(url, { credentials: "include" });
  if (!res.ok || !res.body) throw new Error(`stream failed ${res.status}`);
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let full = "";
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n");
    buffer = parts.pop() ?? "";
    for (const line of parts) {
      const trimmed = line.trim();
      if (!trimmed.startsWith("data:")) continue;
      const data = trimmed.slice(5).trim();
      if (!data || data === "[DONE]") continue;
      full += data;
      onChunk(full);
    }
  }
  return full;
}

export function LectureViewerClient({ lectureId }: Props) {
  const t = useTranslations("student.lecture_viewer");
  const locale = useLocale();
  const language = localeToTtsLang(locale);
  const { mounted, token } = useClientAuth();
  const queryClient = useQueryClient();
  const sessionIdRef = useRef<string | null>(null);
  const [voiceMode, setVoiceMode] = useState(false);
  const [activeSpan, setActiveSpan] = useState<LectureAudioAlignmentSpan | null>(null);
  const [audioCache, setAudioCache] = useState<LectureAudioCacheRead | null>(null);
  const [selection, setSelection] = useState<HighlightSelection | null>(null);
  const [activeQuestion, setActiveQuestion] = useState<StudentQuestionRead | null>(null);
  const [streamingText, setStreamingText] = useState<string | undefined>(undefined);
  const [panelOpen, setPanelOpen] = useState(false);
  const paragraphRefs = useRef<Map<string, HTMLElement>>(new Map());

  const viewerQuery = useQuery({
    queryKey: ["student", "lecture-viewer", lectureId],
    queryFn: () => studentLecturesApi.openViewer(token!, lectureId, "text"),
    enabled: mounted && !!token && !!lectureId,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  });

  const questionsQuery = useQuery({
    queryKey: ["student", "lecture-questions", lectureId],
    queryFn: () => studentQuestionsApi.list(token!, lectureId),
    enabled: mounted && !!token && !!lectureId,
  });

  useEffect(() => {
    sessionIdRef.current = viewerQuery.data?.session.id ?? null;
  }, [viewerQuery.data?.session.id]);

  useEffect(() => {
    if (!token || !sessionIdRef.current) return;
    const id = window.setInterval(() => {
      const sid = sessionIdRef.current;
      if (!sid) return;
      void studentLecturesApi.touchSession(token, sid).catch(() => undefined);
    }, 60_000);
    return () => window.clearInterval(id);
  }, [token, viewerQuery.data?.session.id]);

  useEffect(() => {
    if (!token) return;
    const onUnload = () => {
      const sid = sessionIdRef.current;
      if (!sid) return;
      const url = `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1"}/students/me/lectures/sessions/${sid}/end`;
      try {
        void fetch(url, { method: "POST", credentials: "include", keepalive: true });
      } catch {
        // ignore
      }
    };
    window.addEventListener("pagehide", onUnload);
    return () => window.removeEventListener("pagehide", onUnload);
  }, [token]);

  const setModeMutation = useMutation({
    mutationFn: (mode: "text" | "voice") =>
      studentLecturesApi.setMode(token!, sessionIdRef.current!, mode),
  });

  useEffect(() => {
    if (!voiceMode || !token) return;
    let cancelled = false;
    let timer: number | undefined;

    const poll = async () => {
      try {
        let cache = await studentLecturesApi.requestAudio(token, lectureId, language);
        while (!cancelled && cache.status === "pending") {
          await new Promise((r) => {
            timer = window.setTimeout(r, 1500);
          });
          cache = await studentLecturesApi.getAudio(token, lectureId, language);
        }
        if (!cancelled) setAudioCache(cache);
      } catch {
        if (!cancelled) setAudioCache(null);
      }
    };
    void poll();
    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
  }, [voiceMode, token, lectureId, language]);

  const toggleVoice = async () => {
    const next = !voiceMode;
    setVoiceMode(next);
    if (!next) {
      setActiveSpan(null);
      setAudioCache(null);
    }
    const sid = sessionIdRef.current;
    if (sid && token) {
      await setModeMutation.mutateAsync(next ? "voice" : "text").catch(() => undefined);
    }
  };

  const onActiveSpanChange = useCallback((span: LectureAudioAlignmentSpan | null) => {
    setActiveSpan(span);
    if (span?.paragraph_id) {
      const el = paragraphRefs.current.get(span.paragraph_id);
      if (el && typeof el.scrollIntoView === "function") {
        el.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    }
  }, []);

  const paragraphs = useMemo(() => {
    const list = viewerQuery.data?.paragraphs ?? [];
    return [...list].sort((a, b) => a.ordinal - b.ordinal);
  }, [viewerQuery.data?.paragraphs]);

  const openAnswerStream = useCallback(
    async (question: StudentQuestionRead) => {
      setActiveQuestion(question);
      setPanelOpen(true);
      setStreamingText("");
      try {
        const url = studentQuestionsApi.streamAnswerUrl(lectureId, question.id);
        await readSseAnswer(url, setStreamingText);
        const refreshed = await studentQuestionsApi.list(token!, lectureId);
        const latest = refreshed.find((q) => q.id === question.id) ?? question;
        setActiveQuestion(latest);
        void queryClient.invalidateQueries({
          queryKey: ["student", "lecture-questions", lectureId],
        });
      } catch {
        // leave panel open with whatever we have
      } finally {
        setStreamingText(undefined);
      }
    },
    [lectureId, queryClient, token]
  );

  const onMouseUpSelect = () => {
    const sel = window.getSelection();
    const text = sel?.toString().trim() ?? "";
    if (text.length < 2) return;
    let paragraphId: string | null = null;
    let node: Node | null = sel?.anchorNode ?? null;
    while (node) {
      if (node instanceof HTMLElement && node.dataset.testid === "lecture-paragraph") {
        paragraphId = node.dataset.paragraphId ?? null;
        break;
      }
      node = node.parentNode;
    }
    const paragraph = paragraphs.find((p) => p.id === paragraphId);
    setSelection({
      text,
      paragraphId,
      sourceChunkId: null,
      // source chunk resolved server-side from paragraph metadata when paragraph_id set
    });
    void paragraph;
  };

  const submitQuestion = async (payload: {
    question_text: string;
    highlight_text: string;
    paragraph_id: string | null;
    source_chunk_id: string | null;
    question_language: "en" | "ur" | "sd" | "ps";
  }) => {
    const sid = sessionIdRef.current;
    if (!token || !sid) return;
    const idem = crypto.randomUUID();
    const created = await studentQuestionsApi.ask(
      token,
      lectureId,
      sid,
      {
        question_text: payload.question_text,
        highlight_text: payload.highlight_text,
        paragraph_id: payload.paragraph_id,
        source_chunk_id: payload.source_chunk_id,
        question_language: payload.question_language,
      },
      idem
    );
    setSelection(null);
    await openAnswerStream(created);
  };

  const onFollowUp = async (content: string) => {
    if (!token || !activeQuestion) return;
    const updated = await studentQuestionsApi.followUp(
      token,
      lectureId,
      activeQuestion.id,
      content,
      crypto.randomUUID()
    );
    await openAnswerStream(updated);
  };

  if (viewerQuery.isLoading) {
    return (
      <p className="text-sm text-gray-500" data-testid="lecture-viewer-loading">
        {t("loading")}
      </p>
    );
  }

  if (viewerQuery.isError) {
    return (
      <div className="space-y-2" data-testid="lecture-viewer-error">
        <p className="text-sm text-red-600">{t("error")}</p>
        <a href="/student" className="text-sm text-blue-600 hover:underline">
          {t("back_dashboard")}
        </a>
      </div>
    );
  }

  const viewer = viewerQuery.data;
  if (!viewer) return null;

  const downloadHref = studentLecturesApi.downloadAudioPath(lectureId, language);

  return (
    <div className="flex min-h-[70vh] flex-col" data-testid="lecture-viewer" dir="auto">
      <article className="mx-auto w-full max-w-3xl flex-1 space-y-6 px-4 pb-28 pt-4">
        <header className="space-y-3 border-b border-gray-200 pb-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-xs font-medium uppercase tracking-wide text-gray-500">
              {voiceMode ? t("mode_voice") : t("mode_text")}
            </p>
            <button
              type="button"
              onClick={() => void toggleVoice()}
              className="rounded-md border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-800 hover:bg-gray-50"
              data-testid="voice-mode-toggle"
              aria-pressed={voiceMode}
            >
              {voiceMode ? t("voice_off") : t("voice_on")}
            </button>
          </div>
          <h1 className="text-2xl font-semibold text-gray-900">{viewer.title}</h1>
          <p className="text-sm text-gray-600">{t("topic_line", { topic: viewer.topic })}</p>
          {token ? <TeacherShareToggle token={token} /> : null}
          <a href="/student" className="inline-block text-sm text-blue-600 hover:underline">
            {t("back_dashboard")}
          </a>
          <TeacherShareToggle token={token!} />
        </header>

        <div
          className="space-y-5"
          data-testid="lecture-paragraphs"
          onMouseUp={onMouseUpSelect}
        >
          {paragraphs.map((paragraph) => {
            const isActive =
              voiceMode && activeSpan != null && activeSpan.paragraph_id === paragraph.id;
            return (
              <section
                key={paragraph.id}
                ref={(el) => {
                  if (el) paragraphRefs.current.set(paragraph.id, el);
                  else paragraphRefs.current.delete(paragraph.id);
                }}
                className={`space-y-2 rounded-md p-2 transition-colors ${
                  isActive ? "bg-amber-50 ring-1 ring-amber-200" : ""
                }`}
                data-testid="lecture-paragraph"
                data-paragraph-id={paragraph.id}
                data-ordinal={paragraph.ordinal}
                data-active={isActive ? "true" : "false"}
              >
                <div className="flex flex-wrap items-center gap-2">
                  <SourceBadge paragraph={paragraph} t={t} />
                </div>
                <p className="whitespace-pre-wrap text-base leading-relaxed text-gray-900">
                  {paragraph.text}
                </p>
                {isActive && activeSpan ? (
                  <p
                    className="text-sm font-medium text-amber-900"
                    data-testid="karaoke-active-sentence"
                  >
                    {activeSpan.text}
                  </p>
                ) : null}
              </section>
            );
          })}
        </div>
      </article>

      <QuestionsTab
        questions={questionsQuery.data ?? []}
        loading={questionsQuery.isLoading}
        onOpen={(q) => {
          setActiveQuestion(q);
          setPanelOpen(true);
          if (!q.answer_text) void openAnswerStream(q);
        }}
      />

      {voiceMode && audioCache?.status === "ready" ? (
        <KaraokePlayer
          audio={audioCache}
          downloadHref={downloadHref}
          onActiveSpanChange={onActiveSpanChange}
          active={voiceMode}
        />
      ) : null}
      {voiceMode && audioCache?.status === "pending" ? (
        <p className="px-4 pb-4 text-center text-sm text-gray-500" data-testid="karaoke-waiting">
          {t("audio_preparing")}
        </p>
      ) : null}
      {voiceMode && audioCache?.status === "failed" ? (
        <p className="px-4 pb-4 text-center text-sm text-red-600" data-testid="karaoke-failed">
          {t("audio_failed")}
        </p>
      ) : null}

      {selection ? (
        <HighlightQuestionBox
          selection={selection}
          onCancel={() => setSelection(null)}
          onSubmit={submitQuestion}
        />
      ) : null}

      <AnswerSidePanel
        question={activeQuestion}
        streamingText={streamingText}
        open={panelOpen}
        onClose={() => {
          setPanelOpen(false);
          setStreamingText(undefined);
        }}
        onFollowUp={onFollowUp}
        onSourceBadgeClick={(chunkId) => {
          if (!chunkId) return;
          const match = paragraphs.find((p) => p.id === chunkId);
          if (match) {
            paragraphRefs.current.get(match.id)?.scrollIntoView({
              behavior: "smooth",
              block: "center",
            });
          }
        }}
      />
    </div>
  );
}
