"use client";

import { useLocale, useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  studentHighlightsApi,
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
import { marksByParagraph, segmentParagraph, selectionOffsetWithin } from "./highlight-marks";
import { QuestionsTab } from "./QuestionsTab";
import { TeacherShareToggle } from "./TeacherShareToggle";
import {
  LiveFeedbackPanel,
  StuckNudge,
  useLiveFeedbackSocket,
  type LiveFeedbackMetrics,
} from "./LiveFeedbackPanel";

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
  const [liveMetrics, setLiveMetrics] = useState<LiveFeedbackMetrics | null>(null);
  const [feedbackCollapsed, setFeedbackCollapsed] = useState(false);
  const [stuckOpen, setStuckOpen] = useState(false);
  const stuckFiredRef = useRef(false);
  const lastPageRef = useRef<string | null>(null);

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

  // T-185: persisted highlights → yellow marks. Failure here must never block
  // the lecture text, so an error simply renders no marks.
  const highlightsQuery = useQuery({
    queryKey: ["student", "lecture-highlights", lectureId],
    queryFn: () => studentHighlightsApi.listForLecture(token!, lectureId),
    enabled: mounted && !!token && !!lectureId,
  });
  const marks = useMemo(
    () => marksByParagraph(Array.isArray(highlightsQuery.data) ? highlightsQuery.data : []),
    [highlightsQuery.data],
  );

  // T-188: "Open in lecture" from My Highlights → ?highlight=<id> scrolls to
  // (and focuses) that yellow mark once it renders. If the mark was dropped
  // after a re-edit (§5.5) there is nothing to scroll to — the lecture just opens.
  const deepLinkDoneRef = useRef(false);
  useEffect(() => {
    if (deepLinkDoneRef.current || !highlightsQuery.data || !viewerQuery.data) return;
    const target = new URLSearchParams(window.location.search).get("highlight");
    if (!target) return;
    const el = document.querySelector<HTMLElement>(
      `[data-testid="highlight-mark"][data-highlight-id="${CSS.escape(target)}"]`,
    );
    deepLinkDoneRef.current = true;
    if (!el) return;
    el.setAttribute("tabindex", "-1");
    if (typeof el.scrollIntoView === "function") {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
    }
    el.focus({ preventScroll: true });
  }, [highlightsQuery.data, viewerQuery.data]);

  useEffect(() => {
    sessionIdRef.current = viewerQuery.data?.session.id ?? null;
  }, [viewerQuery.data?.session.id]);

  useEffect(() => {
    const sid = viewerQuery.data?.session.id;
    if (!sid) return;
    const key = `live-feedback-collapsed:${sid}`;
    setFeedbackCollapsed(sessionStorage.getItem(key) === "1");
  }, [viewerQuery.data?.session.id]);

  const onLiveMetrics = useCallback((m: LiveFeedbackMetrics) => {
    setLiveMetrics(m);
    if (m.stuck_nudge?.should_show && !stuckFiredRef.current) {
      stuckFiredRef.current = true;
      setStuckOpen(true);
    }
  }, []);

  useLiveFeedbackSocket(
    mounted && !!token && !!viewerQuery.data?.session.id,
    onLiveMetrics,
  );

  useEffect(() => {
    if (!token || !sessionIdRef.current) return;
    const sid = sessionIdRef.current;
    const firstPara = viewerQuery.data?.paragraphs?.[0]?.id;
    if (!firstPara || lastPageRef.current === firstPara) return;
    lastPageRef.current = firstPara;
    const api = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
    void fetch(`${api}/students/me/lectures/sessions/${sid}/events`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        event_type: "page_change",
        lecture_id: lectureId,
        page_id: firstPara,
        paragraph_id: firstPara,
      }),
    }).catch(() => undefined);
  }, [token, lectureId, viewerQuery.data?.paragraphs, viewerQuery.data?.session.id]);

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
    let textEl: Element | null = null;
    let node: Node | null = sel?.anchorNode ?? null;
    while (node) {
      if (node instanceof HTMLElement && node.dataset.testid === "lecture-paragraph") {
        paragraphId = node.dataset.paragraphId ?? null;
        textEl = node.querySelector('[data-testid="lecture-paragraph-text"]');
        break;
      }
      node = node.parentNode;
    }
    // T-185: anchor offset inside the paragraph text (server re-verifies it).
    let offset: number | null = null;
    if (textEl && sel && sel.rangeCount > 0) {
      const range = sel.getRangeAt(0);
      const raw = selectionOffsetWithin(textEl, range);
      if (raw !== null) {
        const leading = (sel.toString().length - sel.toString().trimStart().length) || 0;
        offset = raw + leading;
      }
    }
    setSelection({
      text,
      paragraphId,
      sourceChunkId: null,
      offset,
      // source chunk resolved server-side from paragraph metadata when paragraph_id set
    });
  };

  const submitQuestion = async (payload: {
    question_text: string;
    highlight_text: string;
    highlight_offset: number | null;
    paragraph_id: string | null;
    source_chunk_id: string | null;
    question_language: "en" | "ur" | "sd" | "ps";
    attached_images: string[];
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
        highlight_offset: payload.highlight_offset,
        paragraph_id: payload.paragraph_id,
        source_chunk_id: payload.source_chunk_id,
        question_language: payload.question_language,
        ...(payload.attached_images.length > 0
          ? { attached_images: payload.attached_images }
          : {}),
      },
      idem
    );
    setSelection(null);
    void queryClient.invalidateQueries({
      queryKey: ["student", "lecture-highlights", lectureId],
    });
    await openAnswerStream(created);
  };

  const onFollowUp = async (content: string, attachedImages: string[]) => {
    if (!token || !activeQuestion) return;
    const updated = await studentQuestionsApi.followUp(
      token,
      lectureId,
      activeQuestion.id,
      content,
      crypto.randomUUID(),
      attachedImages
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
                <p
                  className="whitespace-pre-wrap text-base leading-relaxed text-gray-900"
                  data-testid="lecture-paragraph-text"
                >
                  {segmentParagraph(paragraph.text, marks.get(paragraph.id) ?? []).map(
                    (segment, i) =>
                      segment.highlightId ? (
                        <mark
                          key={`${segment.highlightId}-${i}`}
                          className="rounded-sm bg-yellow-200 px-0.5 text-gray-900"
                          data-testid="highlight-mark"
                          data-highlight-id={segment.highlightId}
                          title={t("highlight_mark_label")}
                        >
                          {segment.text}
                        </mark>
                      ) : (
                        <span key={`plain-${i}`}>{segment.text}</span>
                      ),
                  )}
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

      <LiveFeedbackPanel
        sessionId={viewerQuery.data?.session.id ?? sessionIdRef.current}
        metrics={liveMetrics}
        collapsed={feedbackCollapsed}
        onToggleCollapsed={() => {
          const next = !feedbackCollapsed;
          setFeedbackCollapsed(next);
          const sid = sessionIdRef.current;
          if (sid) {
            sessionStorage.setItem(
              `live-feedback-collapsed:${sid}`,
              next ? "1" : "0",
            );
          }
        }}
      />

      <StuckNudge
        open={stuckOpen}
        onDismiss={() => setStuckOpen(false)}
        onRephrase={() => {
          const last = paragraphs[paragraphs.length - 1];
          if (!last) return;
          setSelection({
            text: last.text.slice(0, 280),
            paragraphId: last.id,
            sourceChunkId: null,
            offset: 0,
          });
        }}
        onListConcepts={() => {
          const first = paragraphs[0];
          if (!first) return;
          setSelection({
            text: `List the key concepts in: ${first.text.slice(0, 160)}`,
            paragraphId: first.id,
            sourceChunkId: null,
          });
        }}
        onSwitchVoice={() => {
          if (!voiceMode) void toggleVoice();
        }}
      />
    </div>
  );
}
