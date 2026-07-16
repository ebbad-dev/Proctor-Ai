import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { AppShell } from "@/components/layout/AppShell";
import { GlassCard } from "@/components/common/GlassCard";
import { GlowButton } from "@/components/common/GlowButton";
import { HealthStrip } from "@/components/common/HealthStrip";
import { CameraFeedCard } from "@/components/common/CameraFeedCard";
import { RiskGauge } from "@/components/common/RiskGauge";
import { RiskTrendChart } from "@/components/common/RiskTrendChart";
import { RiskContributorList } from "@/components/common/RiskContributorList";
import { EventTimeline } from "@/components/common/EventTimeline";
import { BrowserActivityTimeline } from "@/components/common/BrowserActivityTimeline";
import { EvidenceGallery } from "@/components/common/EvidenceCard";
import { AssistantPanel } from "@/components/common/AssistantPanel";
import { StatusBadge } from "@/components/common/StatusBadge";
import {
  LoadingSkeleton,
  NoBrowserActivity,
  NoAudioEvents,
  NoEvidence,
} from "@/components/common/States";
import { RiskStoryCard } from "@/components/common/RiskStoryCard";
import {
  useSession,
  useSessions,
  useLiveRisk,
  useEvents,
  useEvidence,
  useBrowserActivity,
  useAudio,
  useHealth,
  useBrowserGuardActive,
  useCameraStreamHealth,
  useProctorStatus,
  useEndSession,
} from "@/lib/queries";
import { api } from "@/lib/api";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PowerOff, ShieldAlert } from "lucide-react";
import type { SystemHealth } from "@/lib/types";

const DEFAULT_HEALTH: SystemHealth = {
  primary_camera: { active: false },
  secondary_camera: { active: false },
  microphone: { active: false },
  browser_guard: { active: false },
  backend: { connected: false },
  database: { connected: false },
  network: { stable: false },
};

export const Route = createFileRoute("/monitor")({
  validateSearch: (search: Record<string, unknown>) => {
    return {
      session_id: search.session_id as string | undefined,
    };
  },
  head: () => ({
    meta: [
      { title: "Live Monitoring · ProctorAI" },
      {
        name: "description",
        content:
          "Live AI proctoring dashboard with cameras, browser activity, and explainable risk.",
      },
    ],
  }),
  component: MonitorPage,
});

function MonitorPage() {
  const search = Route.useSearch();
  const sessionsList = useSessions();

  // Pick the requested session, or the first active one, or fallback to ""
  const derivedSessionId =
    search.session_id ||
    sessionsList.data?.find((s) => s.status === "in_progress")?.id ||
    sessionsList.data?.[0]?.id ||
    "";

  const session = useSession(derivedSessionId);
  const risk = useLiveRisk(derivedSessionId);
  const events = useEvents(derivedSessionId);
  const evidence = useEvidence(derivedSessionId);
  const browser = useBrowserActivity(derivedSessionId);
  const audio = useAudio(derivedSessionId);
  const backendHealth = useHealth();
  const guardHealth = useBrowserGuardActive();
  const proctorStatus = useProctorStatus();
  const endSession = useEndSession(derivedSessionId);
  const primaryStreamHealth = useCameraStreamHealth("primary");
  const secondaryStreamHealth = useCameraStreamHealth("secondary");

  const health: SystemHealth = {
    ...(session.data?.health ?? DEFAULT_HEALTH),
    primary_camera: {
      ...(session.data?.health?.primary_camera ?? DEFAULT_HEALTH.primary_camera),
      active: proctorStatus.data?.primary_camera?.active ?? primaryStreamHealth.data ?? false,
      resolution:
        proctorStatus.data?.primary_camera?.resolution ??
        session.data?.health?.primary_camera?.resolution ??
        DEFAULT_HEALTH.primary_camera.resolution,
      fps:
        proctorStatus.data?.primary_camera?.fps ??
        session.data?.health?.primary_camera?.fps ??
        DEFAULT_HEALTH.primary_camera.fps,
    },
    secondary_camera: {
      ...(session.data?.health?.secondary_camera ?? DEFAULT_HEALTH.secondary_camera),
      active: proctorStatus.data?.secondary_camera?.active ?? secondaryStreamHealth.data ?? false,
      resolution:
        proctorStatus.data?.secondary_camera?.resolution ??
        session.data?.health?.secondary_camera?.resolution,
      fps: proctorStatus.data?.secondary_camera?.fps ?? session.data?.health?.secondary_camera?.fps,
    },
    microphone: {
      active: proctorStatus.data?.microphone?.active ?? DEFAULT_HEALTH.microphone.active,
    },
    browser_guard: {
      active: !!(proctorStatus.data?.browser_guard?.active ?? guardHealth.data?.active),
    },
    backend: { connected: backendHealth.isSuccess },
    database: {
      connected: proctorStatus.data?.database?.connected ?? backendHealth.isSuccess,
      offline_fallback: proctorStatus.data?.database?.offline_fallback,
    },
  };
  const [tick, setTick] = useState(0);
  void tick;

  const videoToken =
    proctorStatus.data?.active_session_id === derivedSessionId
      ? proctorStatus.data.video_access_token
      : null;
  const streamPrimary = api.cameraStreamUrl(derivedSessionId, "primary", videoToken);
  const streamSecondary = api.cameraStreamUrl(derivedSessionId, "secondary", videoToken);

  if (!derivedSessionId && sessionsList.isSuccess) {
    return (
      <AppShell>
        <div className="flex h-[80vh] flex-col items-center justify-center space-y-4">
          <ShieldAlert className="h-12 w-12 text-muted-foreground/50" />
          <h2 className="text-xl font-semibold text-foreground">No active session selected.</h2>
          <p className="text-sm text-muted-foreground">
            Select a session from the dashboard to begin monitoring.
          </p>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="space-y-4">
        {/* Top bar */}
        <GlassCard className="flex flex-wrap items-center gap-3 p-3 md:p-4">
          <div className="flex min-w-0 items-center gap-3">
            <div className="grid h-10 w-10 place-items-center rounded-xl bg-gradient-primary text-primary-foreground">
              <ShieldAlert className="h-5 w-5" />
            </div>
            <div className="min-w-0">
              <div className="truncate text-sm font-semibold">
                {session.data?.student.name ?? "—"} ·{" "}
                <span className="text-muted-foreground">{session.data?.exam.title ?? "—"}</span>
              </div>
              <div className="text-[11px] text-muted-foreground">
                Session {derivedSessionId} · Started{" "}
                {session.data?.started_at
                  ? new Date(session.data.started_at).toLocaleTimeString()
                  : "—"}
              </div>
            </div>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <StatusBadge label={`${session.data?.strictness ?? "—"} strictness`} status="info" />
            <StatusBadge label="Backend connected" status="ok" />
            <Timer startISO={session.data?.started_at} onTick={() => setTick((t) => t + 1)} />
            <GlowButton
              variant="outline"
              size="sm"
              disabled={!derivedSessionId || endSession.isPending}
              onClick={() => endSession.mutate()}
            >
              <PowerOff className="h-4 w-4" /> End exam
            </GlowButton>
          </div>
        </GlassCard>

        <HealthStrip health={health} />

        {risk.data && (
          <RiskStoryCard risk={risk.data} session={session.data ?? undefined} compact />
        )}

        {/* Main 3-column grid */}
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
          {/* Left: cameras */}
          <div className="space-y-4 xl:col-span-5">
            <CameraFeedCard
              label="Primary"
              source="primary"
              active={health.primary_camera.active}
              fps={health.primary_camera.fps}
              resolution={health.primary_camera.resolution}
              streamUrl={streamPrimary}
            />
            <CameraFeedCard
              label="Secondary"
              source="secondary"
              active={health.secondary_camera.active}
              fps={health.secondary_camera.fps}
              resolution={health.secondary_camera.resolution}
              streamUrl={streamSecondary}
            />
          </div>

          {/* Center: risk */}
          <div className="space-y-4 xl:col-span-4">
            <GlassCard className="p-4">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold">Risk analysis</h3>
                <span className="text-[11px] text-muted-foreground">
                  Updated {risk.data ? new Date(risk.data.updated_at).toLocaleTimeString() : "—"}
                </span>
              </div>
              <div className="mt-2 grid place-items-center">
                {risk.data ? (
                  <RiskGauge score={risk.data.score} level={risk.data.level} />
                ) : (
                  <LoadingSkeleton lines={2} />
                )}
              </div>
              <div className="mt-2">
                {risk.data ? <RiskTrendChart data={risk.data.trend} /> : null}
              </div>
            </GlassCard>

            <GlassCard className="p-4">
              <h3 className="mb-3 text-sm font-semibold">Top contributors</h3>
              {risk.data ? (
                <RiskContributorList items={risk.data.contributors} />
              ) : (
                <LoadingSkeleton lines={4} />
              )}
            </GlassCard>
          </div>

          {/* Right: events + assistant */}
          <div className="space-y-4 xl:col-span-3">
            <GlassCard className="p-4">
              <div className="mb-3 flex items-center justify-between">
                <h3 className="text-sm font-semibold">Live events</h3>
                <span className="text-[11px] text-muted-foreground">
                  {events.data?.length ?? 0} events
                </span>
              </div>
              <AnimatePresence mode="popLayout">
                {events.data ? (
                  <EventTimeline events={events.data} limit={6} />
                ) : (
                  <LoadingSkeleton lines={4} />
                )}
              </AnimatePresence>
            </GlassCard>

            <div className="h-[420px]">
              <AssistantPanel embedded />
            </div>
          </div>
        </div>

        {/* Bottom tabs */}
        <GlassCard className="p-2">
          <Tabs defaultValue="evidence">
            <TabsList className="bg-white/5">
              <TabsTrigger value="evidence">Evidence Gallery</TabsTrigger>
              <TabsTrigger value="browser">Browser Activity</TabsTrigger>
              <TabsTrigger value="audio">Audio Events</TabsTrigger>
              <TabsTrigger value="risk">Risk Details</TabsTrigger>
              <TabsTrigger value="logs">System Logs</TabsTrigger>
              <TabsTrigger value="report">Report Preview</TabsTrigger>
            </TabsList>
            <TabsContent value="evidence" className="p-3">
              {!evidence.data ? (
                <LoadingSkeleton lines={3} />
              ) : evidence.data.length === 0 ? (
                <NoEvidence />
              ) : (
                <EvidenceGallery
                  items={evidence.data}
                  events={events.data}
                  browser={browser.data}
                />
              )}
            </TabsContent>
            <TabsContent value="browser" className="p-3">
              {!browser.data ? (
                <LoadingSkeleton lines={3} />
              ) : browser.data.length === 0 ? (
                <NoBrowserActivity />
              ) : (
                <BrowserActivityTimeline items={browser.data} />
              )}
            </TabsContent>
            <TabsContent value="audio" className="p-3">
              {!audio.data ? (
                <LoadingSkeleton lines={3} />
              ) : audio.data.length === 0 ? (
                <NoAudioEvents />
              ) : (
                <ul className="space-y-2 text-sm">
                  {audio.data.map((a) => (
                    <li
                      key={a.id}
                      className="flex items-center gap-3 rounded-xl border border-white/5 bg-white/[0.03] p-3"
                    >
                      <span className="rounded-md bg-primary/15 px-2 py-1 text-xs uppercase tracking-wider text-primary">
                        {a.type.replace("_", " ")}
                      </span>
                      <span className="text-muted-foreground">
                        {(a.duration_ms / 1000).toFixed(1)}s · confidence{" "}
                        {(a.confidence * 100).toFixed(0)}%
                      </span>
                      <span className="ml-auto font-mono text-primary">+{a.risk_impact}</span>
                    </li>
                  ))}
                </ul>
              )}
            </TabsContent>
            <TabsContent value="risk" className="p-3">
              {risk.data && <RiskContributorList items={risk.data.contributors} />}
            </TabsContent>
            <TabsContent value="logs" className="p-3">
              <pre className="overflow-x-auto rounded-xl border border-white/5 bg-black/40 p-3 text-[11px] leading-relaxed text-muted-foreground">
                {[
                  `[backend] ${backendHealth.isSuccess ? "connected" : backendHealth.isError ? "unreachable" : "checking"}`,
                  `[proctor] ${proctorStatus.data?.engine_running ? "running" : "not running"}`,
                  `[session] ${derivedSessionId || "none"}`,
                  `[risk] events=${events.data?.length ?? 0} score=${risk.data?.score ?? 0}`,
                  `[camera] primary=${health.primary_camera.active ? "active" : "inactive"} secondary=${health.secondary_camera.active ? "active" : "inactive"}`,
                  `[microphone] ${health.microphone.active ? "active" : "inactive"}`,
                  `[browser_guard] ${health.browser_guard.active ? "active" : "inactive"}`,
                  `[database] ${health.database.connected ? "connected" : "offline"}`,
                  proctorStatus.data?.phone_detection
                    ? `[object_detection] ${proctorStatus.data.phone_detection.status}${proctorStatus.data.phone_detection.reason ? ` - ${proctorStatus.data.phone_detection.reason}` : ""}`
                    : "[object_detection] unknown",
                ].join("\n")}
              </pre>
            </TabsContent>
            <TabsContent value="report" className="p-3">
              <Link to="/reports" search={{ session_id: derivedSessionId || undefined }}>
                <GlowButton variant="primary">Open full report</GlowButton>
              </Link>
            </TabsContent>
          </Tabs>
        </GlassCard>
      </div>
    </AppShell>
  );
}

function Timer({ startISO, onTick }: { startISO?: string; onTick: () => void }) {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    if (!startISO) return;
    const id = setInterval(() => {
      setElapsed(Math.floor((Date.now() - new Date(startISO).getTime()) / 1000));
      onTick();
    }, 1000);
    return () => clearInterval(id);
  }, [startISO, onTick]);
  const h = Math.floor(elapsed / 3600);
  const m = Math.floor((elapsed % 3600) / 60);
  const s = elapsed % 60;
  return (
    <span className="font-mono text-sm text-foreground" aria-label="Elapsed session time">
      {String(h).padStart(2, "0")}:{String(m).padStart(2, "0")}:{String(s).padStart(2, "0")}
    </span>
  );
}
