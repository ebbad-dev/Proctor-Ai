import { createFileRoute } from "@tanstack/react-router";
import { motion } from "framer-motion";
import { AppShell } from "@/components/layout/AppShell";
import { GlassCard } from "@/components/common/GlassCard";
import { GlowButton } from "@/components/common/GlowButton";
import { StatusBadge } from "@/components/common/StatusBadge";
import { EventTimeline } from "@/components/common/EventTimeline";
import { EvidenceGallery } from "@/components/common/EvidenceCard";
import { BrowserActivityTimeline } from "@/components/common/BrowserActivityTimeline";
import { useGenerateReport, useReport, useSession, useSessions } from "@/lib/queries";
import { LoadingSkeleton } from "@/components/common/States";
import { Download, Sparkles } from "lucide-react";
import { ParticleField } from "@/components/effects/ParticleField";
import { useState } from "react";
import { api } from "@/lib/api";

export const Route = createFileRoute("/reports")({
  validateSearch: (search: Record<string, unknown>) => ({
    session_id: search.session_id as string | undefined,
  }),
  head: () => ({
    meta: [
      { title: "Report Viewer - ProctorAI" },
      {
        name: "description",
        content: "Audit-ready proctoring report with evidence, browser activity, and risk verdict.",
      },
    ],
  }),
  component: ReportPage,
});

function ReportPage() {
  const search = Route.useSearch();
  const sessions = useSessions();
  const fallbackSessionId =
    sessions.data?.find((s) => s.status === "completed")?.id ?? sessions.data?.[0]?.id ?? "";
  const sessionId = search.session_id ?? fallbackSessionId;
  const report = useReport(sessionId);
  const generateReport = useGenerateReport(sessionId);
  const session = useSession(sessionId);
  const pdfUrl = report.data?.pdf_url;
  const reportMissing = report.isError && !report.data;
  const [downloadError, setDownloadError] = useState("");
  const [downloading, setDownloading] = useState(false);

  const downloadPdf = async () => {
    setDownloadError("");
    setDownloading(true);
    try {
      await api.downloadReport(sessionId);
    } catch (error) {
      setDownloadError(error instanceof Error ? error.message : "Report download failed.");
    } finally {
      setDownloading(false);
    }
  };

  return (
    <AppShell>
      <div className="space-y-4">
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
          <GlassCard className="relative overflow-hidden p-6">
            <ParticleField count={20} />
            <div className="relative flex flex-wrap items-center gap-4">
              <div className="grid h-14 w-14 place-items-center rounded-2xl bg-gradient-primary text-primary-foreground shadow-glow">
                <Sparkles className="h-7 w-7" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="text-xs uppercase tracking-widest text-muted-foreground">
                  Audit-ready report
                </div>
                <h1 className="text-2xl font-bold">
                  Session {sessionId || "-"}{" "}
                  <span className="text-gradient">{session.data?.student.name ?? "-"}</span>
                </h1>
                <p className="mt-1 text-sm text-muted-foreground">
                  {sessionId
                    ? report.data?.summary ||
                      (reportMissing
                        ? "No PDF report exists yet. Generate one from this session's live data."
                        : "Checking report status...")
                    : "No session selected."}
                </p>
              </div>
              <div className="flex items-center gap-2">
                {report.data && (
                  <StatusBadge
                    label={`Verdict: ${report.data.verdict}`}
                    level={report.data.verdict}
                  />
                )}
                {pdfUrl ? (
                  <GlowButton disabled={downloading} onClick={() => void downloadPdf()}>
                    <Download className="h-4 w-4" /> {downloading ? "Downloading..." : "Download PDF"}
                  </GlowButton>
                ) : (
                  <GlowButton
                    disabled={!sessionId || generateReport.isPending}
                    onClick={() => generateReport.mutate()}
                  >
                    <Download className="h-4 w-4" />{" "}
                    {generateReport.isPending ? "Generating..." : "Generate PDF"}
                  </GlowButton>
                )}
              </div>
            </div>
            {generateReport.isError && (
              <p className="relative mt-4 rounded-lg border border-red-400/30 bg-red-400/10 p-3 text-xs text-red-200">
                Report generation failed. Confirm the backend is running and the reporting
                dependencies are installed.
              </p>
            )}
            {downloadError && (
              <p className="relative mt-4 rounded-lg border border-red-400/30 bg-red-400/10 p-3 text-xs text-red-200">
                {downloadError}
              </p>
            )}
          </GlassCard>
        </motion.div>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <GlassCard className="p-4 lg:col-span-2">
            <h3 className="mb-3 text-sm font-semibold">Event timeline</h3>
            {session.data ? (
              <EventTimeline events={session.data.events} />
            ) : (
              <LoadingSkeleton lines={5} />
            )}
          </GlassCard>
          <GlassCard className="p-4">
            <h3 className="mb-3 text-sm font-semibold">Browser activity</h3>
            {session.data ? (
              <BrowserActivityTimeline items={session.data.browser_activity} />
            ) : (
              <LoadingSkeleton lines={5} />
            )}
          </GlassCard>
        </div>

        <GlassCard className="p-4">
          <h3 className="mb-3 text-sm font-semibold">Evidence</h3>
          {session.data ? (
            <EvidenceGallery items={session.data.evidence} />
          ) : (
            <LoadingSkeleton lines={4} />
          )}
        </GlassCard>

        <GlassCard className="p-4">
          <h3 className="text-sm font-semibold">Audio summary</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            {session.data?.audio_events.length ?? 0} audio anomalies detected during the session.
          </p>
        </GlassCard>

        <p className="rounded-xl border border-white/10 bg-white/5 p-3 text-xs text-muted-foreground">
          This report is generated by ProctorAI's rule-based risk engine. Final academic decisions
          must be made by an authorized instructor.
        </p>
      </div>
    </AppShell>
  );
}
