import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { AppShell } from "@/components/layout/AppShell";
import { GlassCard } from "@/components/common/GlassCard";
import { GlowButton } from "@/components/common/GlowButton";
import { StatusBadge } from "@/components/common/StatusBadge";
import type { ChecklistItemState } from "@/lib/types";
import { useBrowserGuardActive, useCameraStreamHealth, useEvidence, useHealth, useProctorStatus, useSessions } from "@/lib/queries";
import { AlertTriangle, CheckCircle2, ShieldOff } from "lucide-react";
import { cn } from "@/lib/utils";

const statusMap = {
  passed: { label: "Passed", status: "ok" as const, icon: CheckCircle2 },
  warning: { label: "Warning", status: "warning" as const, icon: AlertTriangle },
  failed: { label: "Failed", status: "error" as const, icon: ShieldOff },
  optional: { label: "Optional", status: "idle" as const, icon: CheckCircle2 },
};

export const Route = createFileRoute("/checklist")({
  head: () => ({
    meta: [
      { title: "Secure Exam Checklist · ProctorAI" },
      {
        name: "description",
        content: "Verify camera, mic, Browser Guard, and network before starting your exam.",
      },
    ],
  }),
  component: ChecklistPage,
});

function ChecklistPage() {
  const [fullscreen, setFullscreen] = useState(false);
  const [online, setOnline] = useState(true);
  const health = useHealth();
  const guard = useBrowserGuardActive();
  const primaryCamera = useCameraStreamHealth("primary");
  const proctor = useProctorStatus();
  const sessions = useSessions();
  const sessionId = sessions.data?.find((session) => session.status === "in_progress")?.id ?? "";
  const evidence = useEvidence(sessionId);

  useEffect(() => {
    const updateFullscreen = () => setFullscreen(!!document.fullscreenElement);
    const updateOnline = () => setOnline(navigator.onLine);
    document.addEventListener("fullscreenchange", updateFullscreen);
    window.addEventListener("online", updateOnline);
    window.addEventListener("offline", updateOnline);
    updateFullscreen();
    updateOnline();
    return () => {
      document.removeEventListener("fullscreenchange", updateFullscreen);
      window.removeEventListener("online", updateOnline);
      window.removeEventListener("offline", updateOnline);
    };
  }, []);

  const items = useMemo<ChecklistItemState[]>(() => {
    const backendStatus: ChecklistItemState["status"] = health.isSuccess
      ? "passed"
      : health.isError
        ? "failed"
        : "warning";
    const browserStatus: ChecklistItemState["status"] = guard.data?.active ? "passed" : "warning";
    const cameraStatus: ChecklistItemState["status"] = primaryCamera.data ? "passed" : "warning";
    const evidenceTypes = new Set((evidence.data ?? []).map((item) => item.type));
    const hasFace = evidenceTypes.has("face");
    const hasId = evidenceTypes.has("id_card");
    const hasRoom = evidenceTypes.has("room_scan");

    return [
      {
        id: "1",
        label: "Primary camera active",
        description: primaryCamera.data ? "Front-facing webcam stream is reachable." : "MJPEG camera stream is not reachable yet.",
        status: cameraStatus,
      },
      {
        id: "2",
        label: "Secondary camera",
        description: proctor.data?.secondary_camera?.active ? "Side-angle webcam is active." : "No optional secondary camera is configured.",
        status: proctor.data?.secondary_camera?.active ? "passed" : "optional",
      },
      {
        id: "3",
        label: "Microphone active",
        description: proctor.data?.microphone?.active ? "Microphone capture is active." : "Microphone capture is not active.",
        status: proctor.data?.microphone?.active ? "passed" : "warning",
      },
      {
        id: "4",
        label: "Browser Guard active",
        description: guard.data?.active ? "Exact tab and URL tracking is connected." : "Fallback browser monitoring is available; exact URL tracking is offline.",
        status: browserStatus,
        fix_action: "Open Browser Guard",
      },
      {
        id: "5",
        label: "Fullscreen active",
        description: fullscreen ? "The current page is in fullscreen mode." : "Enter fullscreen before beginning the exam.",
        status: fullscreen ? "passed" : "warning",
        fix_action: "Enter fullscreen",
      },
      {
        id: "6",
        label: "Backend connected",
        description: health.isSuccess ? "FastAPI is reachable." : health.isError ? "FastAPI is not reachable." : "Checking FastAPI status.",
        status: backendStatus,
        critical: true,
      },
      {
        id: "7",
        label: "Database connected",
        description: proctor.data?.database?.connected ? "SQL persistence is active." : "The persistent database is unavailable.",
        status: proctor.data?.database?.connected ? "passed" : "failed",
        critical: true,
      },
      {
        id: "8",
        label: "Network available",
        description: online ? "The browser reports an active network connection." : "The browser is offline.",
        status: online ? "passed" : "failed",
        critical: true,
      },
      {
        id: "9",
        label: "ID verification",
        description: hasFace && hasId ? "Face and university ID evidence are stored for the active session." : "Face and university ID evidence have not been stored for an active session.",
        status: hasFace && hasId ? "passed" : "warning",
        fix_action: "Capture identity",
      },
      {
        id: "10",
        label: "Room scan",
        description: hasRoom ? "Room scan evidence is stored for the active session." : "Room scan evidence has not been stored for an active session.",
        status: hasRoom ? "passed" : "warning",
        fix_action: "Capture room",
      },
      {
        id: "11",
        label: "Evidence persistence",
        description: health.isSuccess && proctor.data?.database?.connected ? "Evidence API and database are reachable." : "Evidence persistence is not ready.",
        status: health.isSuccess && proctor.data?.database?.connected ? "passed" : "failed",
        critical: true,
      },
    ];
  }, [evidence.data, fullscreen, guard.data?.active, health.isError, health.isSuccess, online, primaryCamera.data, proctor.data]);

  const hasFailure = items.some((i) => i.status === "failed");

  return (
    <AppShell>
      <div className="mx-auto max-w-4xl space-y-4">
        <GlassCard className="flex flex-wrap items-center gap-3 p-4">
          <div>
            <h1 className="text-lg font-semibold">Secure exam checklist</h1>
            <p className="text-xs text-muted-foreground">Live status from the current browser, proctor engine, and database.</p>
          </div>
        </GlassCard>

        {!guard.data?.active && (
          <div className="rounded-xl border border-amber-400/30 bg-amber-400/10 p-3 text-sm text-amber-200">
            <strong>Browser Guard inactive</strong> - exact tab and URL tracking is unavailable. Fallback
            tab, focus, clipboard, devtools, and fullscreen monitoring remains active during an exam.
          </div>
        )}
        {hasFailure && (
          <div className="rounded-xl border border-red-400/30 bg-red-400/10 p-3 text-sm text-red-200">
            <strong>Live checks failed</strong> - start the backend services before beginning a live
            exam.
          </div>
        )}

        <div className="grid grid-cols-1 gap-2">
          {items.map((it, idx) => {
            const s = statusMap[it.status];
            const Icon = s.icon;
            return (
              <motion.div
                key={it.id}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: idx * 0.03 }}
              >
                <GlassCard
                  className={cn(
                    "flex items-center gap-3 p-3",
                    it.critical && it.status === "warning" && "animate-pulse-glow",
                  )}
                >
                  <div
                    className={cn(
                      "grid h-9 w-9 place-items-center rounded-lg",
                      it.status === "passed" && "bg-emerald-400/15 text-emerald-300",
                      it.status === "warning" && "bg-amber-400/15 text-amber-300",
                      it.status === "failed" && "bg-red-400/15 text-red-300",
                      it.status === "optional" && "bg-white/5 text-muted-foreground",
                    )}
                  >
                    <Icon className="h-4 w-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-medium">{it.label}</div>
                    <div className="text-xs text-muted-foreground">{it.description}</div>
                  </div>
                  <StatusBadge label={s.label} status={s.status} />
                  {it.label === "Fullscreen active" && !fullscreen && (
                    <GlowButton
                      variant="outline"
                      size="sm"
                      onClick={() => document.documentElement.requestFullscreen?.().catch(() => undefined)}
                    >
                      Enter fullscreen
                    </GlowButton>
                  )}
                  {it.label === "Browser Guard active" && !guard.data?.active && (
                    <Link to="/browser-guard"><GlowButton variant="outline" size="sm">Open Browser Guard</GlowButton></Link>
                  )}
                  {it.label === "ID verification" && it.status !== "passed" && (
                    sessionId ? (
                      <Link to="/id-verification"><GlowButton variant="outline" size="sm">Capture identity</GlowButton></Link>
                    ) : (
                      <Link to="/setup"><GlowButton variant="outline" size="sm">Complete setup</GlowButton></Link>
                    )
                  )}
                  {it.label === "Room scan" && it.status !== "passed" && (
                    sessionId ? (
                      <Link to="/room-scan"><GlowButton variant="outline" size="sm">Capture room</GlowButton></Link>
                    ) : (
                      <Link to="/setup"><GlowButton variant="outline" size="sm">Complete setup</GlowButton></Link>
                    )
                  )}
                </GlassCard>
              </motion.div>
            );
          })}
        </div>
      </div>
    </AppShell>
  );
}
