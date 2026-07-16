import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { GlassCard } from "@/components/common/GlassCard";
import { GlowButton } from "@/components/common/GlowButton";
import { StatusBadge } from "@/components/common/StatusBadge";
import { LoadingSkeleton } from "@/components/common/States";
import { useAttempt, useBrowserGuardActive, useLiveRisk, useSaveAttemptResponse, useSubmitAttempt } from "@/lib/queries";
import { api } from "@/lib/api";
import { endpoints } from "@/config/endpoints";
import { CheckCircle2, Clock, Eye, ListChecks, Lock, Send, ShieldAlert } from "lucide-react";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/exam")({
  validateSearch: (search: Record<string, unknown>) => ({
    attempt_id: search.attempt_id as string | undefined,
  }),
  head: () => ({
    meta: [
      { title: "Secure Exam - ProctorAI" },
      { name: "description", content: "Browser-native monitored exam workspace." },
    ],
  }),
  component: ExamRunnerPage,
});

function ExamRunnerPage() {
  const navigate = useNavigate();
  const { attempt_id = "" } = Route.useSearch();
  const attempt = useAttempt(attempt_id);
  const saveResponse = useSaveAttemptResponse(attempt_id);
  const submitAttempt = useSubmitAttempt(attempt_id);
  const sessionId = attempt.data?.session_id || "";
  const risk = useLiveRisk(sessionId);
  const guard = useBrowserGuardActive();
  const [activeQuestionId, setActiveQuestionId] = useState("");
  const [submitError, setSubmitError] = useState("");
  const [timeExpired, setTimeExpired] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);

  const questions = attempt.data?.questions ?? [];
  const responseByQuestion = useMemo(() => {
    const map = new Map<string, string>();
    for (const response of attempt.data?.responses ?? []) {
      if (response.selected_option_id) map.set(response.question_id, response.selected_option_id);
    }
    return map;
  }, [attempt.data?.responses]);

  useEffect(() => {
    if (!activeQuestionId && questions[0]) setActiveQuestionId(questions[0].question_id);
  }, [activeQuestionId, questions]);

  useEffect(() => {
    const activeSessionId = attempt.data?.session_id;
    if (!activeSessionId || typeof window === "undefined") return;
    let cancelled = false;
    api.startProctor({
      session_id: activeSessionId,
      student_id: attempt.data?.user_id,
      exam_code: attempt.data?.exam.exam_code || attempt.data?.exam_id,
    })
      .then(() => api.issueBrowserGuardToken(activeSessionId))
      .then(({ token, session_id }) => {
        if (cancelled) return;
        window.postMessage(
          { type: "PROCTORAI_BROWSER_GUARD_TOKEN", token, session_id },
          window.location.origin,
        );
      })
      .catch((exc) => setSubmitError(exc instanceof Error ? exc.message : "Could not start protected exam monitoring."));
    return () => {
      cancelled = true;
      window.postMessage({ type: "PROCTORAI_BROWSER_GUARD_CLEAR" }, window.location.origin);
    };
  }, [attempt.data?.session_id, attempt.data?.user_id, attempt.data?.exam.exam_code, attempt.data?.exam_id]);

  useEffect(() => {
    const updateFullscreen = () => setFullscreen(!!document.fullscreenElement);
    document.addEventListener("fullscreenchange", updateFullscreen);
    updateFullscreen();
    return () => document.removeEventListener("fullscreenchange", updateFullscreen);
  }, []);

  useBrowserEventFallback(sessionId);

  if (!attempt_id) {
    return (
      <AppShell>
        <GlassCard className="mx-auto max-w-xl p-6 text-center">
          <ShieldAlert className="mx-auto h-10 w-10 text-amber-300" />
          <h1 className="mt-3 text-lg font-semibold">No exam attempt selected</h1>
          <p className="mt-2 text-sm text-muted-foreground">Start from the setup checklist to open a monitored attempt.</p>
          <Link to="/setup">
            <GlowButton className="mt-4">Open setup</GlowButton>
          </Link>
        </GlassCard>
      </AppShell>
    );
  }

  if (attempt.isLoading || !attempt.data) {
    return (
      <AppShell>
        <GlassCard className="p-6">
          <LoadingSkeleton lines={8} />
        </GlassCard>
      </AppShell>
    );
  }

  const activeQuestion = questions.find((question) => question.question_id === activeQuestionId) ?? questions[0];
  const answered = responseByQuestion.size;
  const submitted = attempt.data.status === "submitted";

  const submit = async (requireConfirmation = true) => {
    setSubmitError("");
    if (submitAttempt.isPending || submitted) return;
    if (requireConfirmation) {
      const ok = window.confirm("Submit this exam? You will not be able to reattempt after submission.");
      if (!ok) return;
    }
    try {
      const result = await submitAttempt.mutateAsync();
      await api.stopProctor().catch(() => undefined);
      if (result.session_id) navigate({ to: "/sessions/$sessionId", params: { sessionId: result.session_id } });
    } catch (exc) {
      setSubmitError(exc instanceof Error ? exc.message : "Could not submit attempt.");
    }
  };

  return (
    <AppShell>
      <div className="grid gap-4 xl:grid-cols-[280px_1fr_300px]">
        <GlassCard className="p-4">
          <div className="flex items-center gap-2">
            <ListChecks className="h-4 w-4 text-primary" />
            <h2 className="text-sm font-semibold">Questions</h2>
          </div>
          <div className="mt-4 space-y-2">
            {questions.map((question, index) => {
              const isAnswered = responseByQuestion.has(question.question_id);
              const isActive = question.question_id === activeQuestion?.question_id;
              return (
                <button
                  key={question.question_id}
                  type="button"
                  onClick={() => setActiveQuestionId(question.question_id)}
                  className={cn(
                    "flex w-full items-center gap-3 rounded-xl border px-3 py-2 text-left text-sm transition",
                    isActive ? "border-primary/50 bg-primary/10" : "border-white/10 bg-white/[0.03] hover:bg-white/[0.06]",
                  )}
                >
                  <span className="grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-white/5 text-xs">{index + 1}</span>
                  <span className="min-w-0 flex-1 truncate">{question.question_text}</span>
                  {isAnswered && <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-300" />}
                </button>
              );
            })}
          </div>
        </GlassCard>

        <GlassCard className="min-h-[70vh] p-5">
          <div className="flex flex-wrap items-start justify-between gap-3 border-b border-white/10 pb-4">
            <div>
              <div className="text-xs uppercase tracking-wider text-muted-foreground">
                {attempt.data.exam.exam_code || attempt.data.exam_id}
              </div>
              <h1 className="mt-1 text-2xl font-semibold">{attempt.data.exam.title}</h1>
              <div className="mt-2 flex flex-wrap gap-2">
                <StatusBadge label={`Roll ${attempt.data.roll_number}`} status="info" />
                <StatusBadge label={`${answered}/${questions.length} answered`} status={answered === questions.length ? "ok" : "warning"} />
                <StatusBadge label={submitted ? "Submitted" : "In progress"} status={submitted ? "ok" : "warning"} />
              </div>
            </div>
            <ExamTimer
              startedAt={attempt.data.started_at}
              minutes={attempt.data.exam.duration_minutes}
              submitted={submitted}
              onExpire={() => {
                setTimeExpired(true);
                void submit(false);
              }}
            />
          </div>

          {!activeQuestion ? (
            <div className="grid min-h-[360px] place-items-center text-sm text-muted-foreground">
              No questions have been added to this exam.
            </div>
          ) : (
            <div className="py-6">
              <div className="text-sm text-muted-foreground">Question {questions.indexOf(activeQuestion) + 1}</div>
              <h2 className="mt-2 text-xl font-semibold leading-relaxed">{activeQuestion.question_text}</h2>
              <div className="mt-2 text-sm text-primary">{activeQuestion.marks} marks</div>
              <div className="mt-6 space-y-3">
                {activeQuestion.options.map((option, index) => {
                  const selected = responseByQuestion.get(activeQuestion.question_id) === option.option_id;
                  return (
                    <button
                      key={option.option_id}
                      type="button"
                      disabled={submitted || timeExpired || saveResponse.isPending}
                      onClick={() =>
                        saveResponse.mutate({
                          question_id: activeQuestion.question_id,
                          selected_option_id: option.option_id,
                        })
                      }
                      className={cn(
                        "flex w-full items-center gap-3 rounded-2xl border p-4 text-left transition disabled:cursor-not-allowed disabled:opacity-70",
                        selected ? "border-primary/60 bg-primary/15" : "border-white/10 bg-white/[0.035] hover:bg-white/[0.07]",
                      )}
                    >
                      <span className="grid h-8 w-8 place-items-center rounded-xl bg-white/5 text-xs font-semibold">
                        {String.fromCharCode(65 + index)}
                      </span>
                      <span className="flex-1">{option.option_text}</span>
                      {selected && <CheckCircle2 className="h-5 w-5 text-primary" />}
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-white/10 pt-4">
            <p className="text-xs text-muted-foreground">
              Answers autosave immediately. Submission is final and locks reattempts.
            </p>
            <GlowButton disabled={submitted || timeExpired || submitAttempt.isPending || !questions.length} onClick={() => void submit(true)}>
              <Send className="h-4 w-4" />
              {submitAttempt.isPending ? "Submitting..." : submitted ? "Submitted" : "Submit exam"}
            </GlowButton>
          </div>
          {submitError && (
            <p className="mt-3 rounded-lg border border-red-400/30 bg-red-400/10 p-2 text-xs text-red-200">{submitError}</p>
          )}
        </GlassCard>

        <div className="space-y-4">
          <GlassCard className="p-4">
            <div className="flex items-center gap-2">
              <Eye className="h-4 w-4 text-primary" />
              <h3 className="text-sm font-semibold">Live proctoring</h3>
            </div>
            <div className="mt-4 space-y-3 text-sm">
              <Row label="Session" value={sessionId || "Starting"} />
              <Row label="Risk score" value={risk.data ? String(risk.data.score) : "0"} />
              <Row label="Browser monitoring" value={guard.data?.active ? "Enhanced active" : "Fallback active"} />
              <Row
                label="Fullscreen"
                value={fullscreen ? "Active" : "Required"}
              />
            </div>
            <GlowButton
              className="mt-4 w-full"
              variant="outline"
              onClick={() => document.documentElement.requestFullscreen?.().catch(() => undefined)}
            >
              <Lock className="h-4 w-4" />
              Enter fullscreen
            </GlowButton>
          </GlassCard>

          <GlassCard className="p-4">
            <h3 className="text-sm font-semibold">Integrity policy</h3>
            <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
              <li>Tab switches, focus loss, clipboard actions, devtools, and fullscreen exits are logged.</li>
              <li>Camera and microphone monitoring stay bound to this attempt session.</li>
              <li>All submitted answers, evidence, and risk events are visible to instructors.</li>
            </ul>
          </GlassCard>
        </div>
      </div>
    </AppShell>
  );
}

function ExamTimer({
  startedAt,
  minutes,
  submitted,
  onExpire,
}: {
  startedAt?: string | null;
  minutes: number;
  submitted: boolean;
  onExpire: () => void;
}) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, []);
  const start = startedAt ? new Date(startedAt).getTime() : now;
  const end = start + minutes * 60_000;
  const remaining = Math.max(0, end - now);
  const expired = remaining === 0;
  useEffect(() => {
    if (expired && !submitted) onExpire();
  }, [expired, submitted]);
  const mm = Math.floor(remaining / 60_000);
  const ss = Math.floor((remaining % 60_000) / 1000);
  return (
    <div className="flex items-center gap-2 rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3">
      <Clock className="h-4 w-4 text-primary" />
      <span className="font-mono text-lg">{submitted ? "Submitted" : `${String(mm).padStart(2, "0")}:${String(ss).padStart(2, "0")}`}</span>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium">{value}</span>
    </div>
  );
}

function useBrowserEventFallback(sessionId: string) {
  useEffect(() => {
    if (!sessionId || typeof window === "undefined") return;
    let lastAwayAt = 0;
    let lastDevtoolsAt = 0;
    const post = (endpoint: string, payload: Record<string, unknown>) => {
      api.postBrowserSignal(endpoint, { ...payload, session_id: sessionId }).catch(() => undefined);
    };
    const away = () => {
      const now = Date.now();
      if (now - lastAwayAt < 1500) return;
      lastAwayAt = now;
      post(endpoints.tabEvent, { direction: "away" });
    };
    const visibility = () => post(endpoints.tabEvent, { direction: document.hidden ? "away" : "back" });
    const keydown = (event: KeyboardEvent) => {
      const key = event.key.toLowerCase();
      const ctrl = event.ctrlKey || event.metaKey;
      const combo =
        (ctrl && ["c", "v", "x", "a", "w", "n", "t", "u"].includes(key)) ||
        (ctrl && event.shiftKey && ["i", "j"].includes(key)) ||
        event.key === "F12";
      if (!combo) return;
      post(endpoints.keyboardEvent, { combo: `${ctrl ? "Ctrl+" : ""}${event.shiftKey ? "Shift+" : ""}${event.key}` });
      if (["F12", "i", "j", "u"].includes(key)) post(endpoints.devtoolsEvent, { state: "open" });
    };
    const clipboard = (event: ClipboardEvent) => post(endpoints.clipboardEvent, { action: event.type });
    const fullscreen = () => {
      if (!document.fullscreenElement) post(endpoints.fullscreenEvent, { state: "exit" });
    };
    const devtoolsHeuristic = window.setInterval(() => {
      const open = window.outerWidth - window.innerWidth > 160 || window.outerHeight - window.innerHeight > 160;
      if (open && Date.now() - lastDevtoolsAt > 8000) {
        lastDevtoolsAt = Date.now();
        post(endpoints.devtoolsEvent, { state: "open" });
      }
    }, 3000);
    document.addEventListener("visibilitychange", visibility);
    window.addEventListener("blur", away);
    document.addEventListener("keydown", keydown);
    document.addEventListener("copy", clipboard);
    document.addEventListener("cut", clipboard);
    document.addEventListener("paste", clipboard);
    document.addEventListener("fullscreenchange", fullscreen);
    return () => {
      window.clearInterval(devtoolsHeuristic);
      document.removeEventListener("visibilitychange", visibility);
      window.removeEventListener("blur", away);
      document.removeEventListener("keydown", keydown);
      document.removeEventListener("copy", clipboard);
      document.removeEventListener("cut", clipboard);
      document.removeEventListener("paste", clipboard);
      document.removeEventListener("fullscreenchange", fullscreen);
    };
  }, [sessionId]);
}
