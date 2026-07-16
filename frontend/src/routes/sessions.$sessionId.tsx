import { createFileRoute, Link, useParams } from "@tanstack/react-router";
import { useState } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { GlassCard } from "@/components/common/GlassCard";
import { GlowButton } from "@/components/common/GlowButton";
import { StatusBadge } from "@/components/common/StatusBadge";
import { RiskGauge } from "@/components/common/RiskGauge";
import { RiskContributorList } from "@/components/common/RiskContributorList";
import { LaneEventTimeline } from "@/components/common/LaneEventTimeline";
import { EventTimeline } from "@/components/common/EventTimeline";
import { BrowserActivityTimeline } from "@/components/common/BrowserActivityTimeline";
import { EvidenceGallery } from "@/components/common/EvidenceCard";
import { LoadingSkeleton, NoBrowserActivity, NoAudioEvents } from "@/components/common/States";
import { RiskStoryCard } from "@/components/common/RiskStoryCard";
import { StickyReviewBar } from "@/components/common/StickyReviewBar";
import { useExamAttempts, useSession, useSubmitReview } from "@/lib/queries";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { FileText, ScanFace, DoorOpen, Check, XCircle, AlertTriangle, Trash2 } from "lucide-react";

export const Route = createFileRoute("/sessions/$sessionId")({
  head: () => ({
    meta: [
      { title: "Session Review · ProctorAI" },
      {
        name: "description",
        content: "Detailed session review with risk contributors, evidence, and decision tools.",
      },
    ],
  }),
  component: SessionReviewPage,
});

function SessionReviewPage() {
  const { sessionId } = useParams({ from: "/sessions/$sessionId" });
  const { data, isLoading } = useSession(sessionId);
  const attempts = useExamAttempts(data?.exam.id ?? "");
  const review = useSubmitReview(sessionId);
  const [notes, setNotes] = useState("");

  if (isLoading || !data) {
    return (
      <AppShell>
        <LoadingSkeleton lines={8} />
      </AppShell>
    );
  }

  const attempt = attempts.data?.find((row) => row.session_id === sessionId);

  return (
    <AppShell>
      <div className="space-y-4 pb-24">
        <GlassCard className="flex flex-wrap items-center gap-3 p-4">
          <div>
            <div className="text-sm text-muted-foreground">Session {sessionId}</div>
            <h1 className="text-xl font-semibold">
              {data.student.name} · {data.exam.title}
            </h1>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <StatusBadge label={`Risk ${data.risk_score}`} level={data.risk_level} />
            <StatusBadge
              label={data.browser_guard_active ? "Browser Guard active" : "Browser Guard off"}
              status={data.browser_guard_active ? "ok" : "warning"}
            />
            <Link to="/reports" search={{ session_id: sessionId }}>
              <GlowButton variant="outline" size="sm" aria-label="Open report">
                <FileText className="h-4 w-4" /> Open report
              </GlowButton>
            </Link>
          </div>
        </GlassCard>

        <RiskStoryCard risk={data.risk} session={data} />

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <GlassCard className="p-4">
            <h3 className="text-sm font-semibold">Risk overview</h3>
            <div className="mt-2 grid place-items-center">
              <RiskGauge score={data.risk.score} level={data.risk.level} size={200} />
            </div>
          </GlassCard>
          <GlassCard className="p-4 lg:col-span-2">
            <h3 className="mb-3 text-sm font-semibold">Top contributors</h3>
            <RiskContributorList items={data.risk.contributors} />
          </GlassCard>
        </div>

        <GlassCard className="p-2">
          <Tabs defaultValue="lanes">
            <TabsList className="bg-white/5">
              <TabsTrigger value="lanes">Timeline lanes</TabsTrigger>
              <TabsTrigger value="events">Event list</TabsTrigger>
              <TabsTrigger value="evidence">Evidence</TabsTrigger>
              <TabsTrigger value="browser">Browser activity</TabsTrigger>
              <TabsTrigger value="audio">Audio events</TabsTrigger>
              <TabsTrigger value="answers">Answers</TabsTrigger>
              <TabsTrigger value="checks">ID &amp; Room scan</TabsTrigger>
            </TabsList>
            <TabsContent value="lanes" className="p-3">
              <LaneEventTimeline events={data.events} evidence={data.evidence} />
            </TabsContent>
            <TabsContent value="events" className="p-3">
              <EventTimeline events={data.events} />
            </TabsContent>
            <TabsContent value="evidence" className="p-3">
              <EvidenceGallery
                items={data.evidence}
                events={data.events}
                browser={data.browser_activity}
              />
            </TabsContent>
            <TabsContent value="browser" className="p-3">
              {data.browser_activity.length > 0 ? (
                <BrowserActivityTimeline items={data.browser_activity} />
              ) : (
                <NoBrowserActivity />
              )}
            </TabsContent>
            <TabsContent value="audio" className="p-3">
              {data.audio_events.length > 0 ? (
                <ul className="space-y-2 text-sm">
                  {data.audio_events.map((a) => (
                    <li
                      key={a.id}
                      className="flex items-center gap-3 rounded-xl border border-white/5 bg-white/[0.03] p-3"
                    >
                      <span className="rounded-md bg-primary/15 px-2 py-1 text-xs uppercase tracking-wider text-primary">
                        {a.type.replace("_", " ")}
                      </span>
                      <span className="text-muted-foreground">
                        {(a.duration_ms / 1000).toFixed(1)}s · conf{" "}
                        {(a.confidence * 100).toFixed(0)}%
                      </span>
                      <span className="ml-auto font-mono text-primary">+{a.risk_impact}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <NoAudioEvents />
              )}
            </TabsContent>
            <TabsContent value="answers" className="p-3">
              {attempt ? (
                <div className="space-y-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <StatusBadge label={`Roll ${attempt.roll_number}`} status="info" />
                    <StatusBadge label={`${attempt.score}/${attempt.max_score} marks`} status="ok" />
                    <StatusBadge label={attempt.status.replace("_", " ")} status={attempt.status === "submitted" ? "ok" : "warning"} />
                  </div>
                  {attempt.questions.map((question, index) => {
                    const response = attempt.responses.find((row) => row.question_id === question.question_id);
                    const selected = question.options.find((option) => option.option_id === response?.selected_option_id);
                    const correct = question.options.find((option) => option.is_correct);
                    return (
                      <div key={question.question_id} className="rounded-xl border border-white/10 bg-white/[0.03] p-3">
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div className="font-medium">{index + 1}. {question.question_text}</div>
                          <StatusBadge
                            label={`${response?.awarded_marks ?? 0}/${question.marks}`}
                            status={response?.is_correct ? "ok" : "warning"}
                          />
                        </div>
                        <div className="mt-2 grid gap-2 text-sm md:grid-cols-2">
                          <div className="rounded-lg border border-white/10 bg-white/[0.03] p-2">
                            <div className="text-[11px] uppercase tracking-wider text-muted-foreground">Selected</div>
                            <div>{selected?.option_text || "No answer"}</div>
                          </div>
                          <div className="rounded-lg border border-emerald-400/20 bg-emerald-400/10 p-2">
                            <div className="text-[11px] uppercase tracking-wider text-emerald-200">Correct</div>
                            <div>{correct?.option_text || "No correct option stored"}</div>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4 text-sm text-muted-foreground">
                  No answer attempt is linked to this session.
                </div>
              )}
            </TabsContent>
            <TabsContent value="checks" className="grid gap-3 p-3 md:grid-cols-2">
              <GlassCard className="p-4">
                <div className="flex items-center gap-2 text-sm font-semibold">
                  <ScanFace className="h-4 w-4 text-primary" /> ID verification
                </div>
                <div className="mt-2 text-xs text-muted-foreground">
                  {data.id_verification?.verified ? "Verified" : "Not verified"}
                </div>
              </GlassCard>
              <GlassCard className="p-4">
                <div className="flex items-center gap-2 text-sm font-semibold">
                  <DoorOpen className="h-4 w-4 text-primary" /> Room scan
                </div>
                <div className="mt-2 text-xs text-muted-foreground">
                  {data.room_scan?.completed ? "Completed" : "Skipped"}
                </div>
              </GlassCard>
            </TabsContent>
          </Tabs>
        </GlassCard>

        <GlassCard className="p-4">
          <h3 className="text-sm font-semibold">Instructor notes</h3>
          <label className="sr-only" htmlFor="instructor-notes">
            Instructor notes
          </label>
          <textarea
            id="instructor-notes"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Add a note explaining your decision..."
            className="mt-2 h-28 w-full rounded-xl border border-white/10 bg-white/5 p-3 text-sm outline-none placeholder:text-muted-foreground focus:border-primary/40"
          />
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <GlowButton
              onClick={() => review.mutate({ decision: "valid", notes })}
              variant="outline"
              size="sm"
              disabled={review.isPending}
            >
              <Check className="h-4 w-4" /> Valid violation
            </GlowButton>
            <GlowButton
              onClick={() => review.mutate({ decision: "false_positive", notes })}
              variant="ghost"
              size="sm"
              disabled={review.isPending}
            >
              <XCircle className="h-4 w-4" /> False positive
            </GlowButton>
            <GlowButton
              onClick={() => review.mutate({ decision: "needs_review", notes })}
              variant="ghost"
              size="sm"
              disabled={review.isPending}
            >
              <AlertTriangle className="h-4 w-4" /> Manual review recommended
            </GlowButton>
            <GlowButton
              onClick={() => review.mutate({ decision: "dismissed", notes })}
              variant="ghost"
              size="sm"
              disabled={review.isPending}
            >
              <Trash2 className="h-4 w-4" /> Dismiss
            </GlowButton>
          </div>
          {review.isSuccess && (
            <p className="mt-3 rounded-lg border border-emerald-400/30 bg-emerald-400/10 p-2.5 text-[11px] text-emerald-200">
              Review saved for this session.
            </p>
          )}
          {review.isError && (
            <p className="mt-3 rounded-lg border border-red-400/30 bg-red-400/10 p-2.5 text-[11px] text-red-200">
              Review save failed. Confirm the backend is running and try again.
            </p>
          )}
          <p className="mt-3 rounded-lg border border-white/10 bg-white/5 p-2.5 text-[11px] text-muted-foreground">
            ProctorAI provides risk analysis and evidence. Instructor decision required for final
            academic outcome.
          </p>
        </GlassCard>

        <StickyReviewBar session={data} />
      </div>
    </AppShell>
  );
}
