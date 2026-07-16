import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { GlassCard } from "@/components/common/GlassCard";
import { GlowButton } from "@/components/common/GlowButton";
import { useCreateEvidence, useSessions } from "@/lib/queries";
import { Camera, CheckCircle2, Circle } from "lucide-react";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/room-scan")({
  head: () => ({
    meta: [
      { title: "Room Scan - ProctorAI" },
      { name: "description", content: "Capture your environment for exam setup review." },
    ],
  }),
  component: RoomScanPage,
});

const checks = ["Desk visible", "No phone visible", "No notes visible", "No second person visible", "Lighting acceptable"];

function RoomScanPage() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [done, setDone] = useState<Set<string>>(new Set());
  const [streaming, setStreaming] = useState(false);
  const [message, setMessage] = useState("");
  const [messageKind, setMessageKind] = useState<"idle" | "success" | "error">("idle");
  const sessions = useSessions();
  const evidence = useCreateEvidence();
  const sessionId = sessions.data?.find((s) => s.status === "in_progress")?.id ?? sessions.data?.[0]?.id ?? "";

  useEffect(() => () => streamRef.current?.getTracks().forEach((track) => track.stop()), []);

  const startCamera = async () => {
    setMessage("");
    setMessageKind("idle");
    if (!navigator.mediaDevices?.getUserMedia) {
      setMessage("Camera access is not supported by this browser.");
      setMessageKind("error");
      return;
    }
    try {
      streamRef.current?.getTracks().forEach((track) => track.stop());
      const stream = await navigator.mediaDevices.getUserMedia({ video: true });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
        setStreaming(true);
      }
    } catch {
      setStreaming(false);
      setMessage("Camera permission was denied or no camera is available.");
      setMessageKind("error");
    }
  };

  const confirmScan = async () => {
    setMessage("");
    setMessageKind("idle");
    if (!sessionId) {
      setMessage("No exam session is available. Complete exam setup first.");
      setMessageKind("error");
      return;
    }
    if (!videoRef.current || !streaming || videoRef.current.readyState < 2) {
      setMessage("Start an exam session and camera before confirming room scan.");
      setMessageKind("error");
      return;
    }
    const canvas = document.createElement("canvas");
    canvas.width = videoRef.current.videoWidth || 640;
    canvas.height = videoRef.current.videoHeight || 480;
    canvas.getContext("2d")?.drawImage(videoRef.current, 0, 0, canvas.width, canvas.height);
    try {
      await evidence.mutateAsync({
        session_id: sessionId,
        evidence_type: "room_scan",
        label: `Room scan: ${checks.join(", ")}`,
        image_data: canvas.toDataURL("image/jpeg", 0.85),
      });
      setMessage("Room scan evidence saved.");
      setMessageKind("success");
    } catch (exc) {
      setMessage(exc instanceof Error ? exc.message : "Could not save room scan evidence.");
      setMessageKind("error");
    }
  };

  return (
    <AppShell>
      <div className="mx-auto max-w-5xl space-y-4">
        <GlassCard className="overflow-hidden p-0">
          <video ref={videoRef} className="aspect-video w-full bg-black object-cover" muted playsInline />
          <div className="p-4">
            <GlowButton variant="outline" onClick={startCamera}>
              <Camera className="h-4 w-4" /> {streaming ? "Camera active" : "Start camera"}
            </GlowButton>
          </div>
        </GlassCard>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <GlassCard className="p-5">
            <h3 className="text-sm font-semibold">Scan instructions</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              Slowly pan your camera around your desk and surroundings, then confirm each required condition.
            </p>
            {message && (
              <p className={cn(
                "mt-3 rounded-lg border p-2 text-xs",
                messageKind === "error"
                  ? "border-red-400/30 bg-red-400/10 text-red-200"
                  : "border-emerald-400/30 bg-emerald-400/10 text-emerald-200",
              )}>{message}</p>
            )}
          </GlassCard>
          <GlassCard className="p-5">
            <h3 className="text-sm font-semibold">Checklist</h3>
            <ul className="mt-3 space-y-2">
              {checks.map((c) => {
                const isDone = done.has(c);
                return (
                  <li key={c}>
                    <button
                      onClick={() =>
                        setDone((s) => {
                          const n = new Set(s);
                          if (n.has(c)) n.delete(c);
                          else n.add(c);
                          return n;
                        })
                      }
                      className={cn("flex w-full items-center gap-3 rounded-xl border border-white/5 bg-white/[0.03] p-2.5 text-left text-sm", isDone && "border-primary/40 bg-primary/10")}
                    >
                      {isDone ? <CheckCircle2 className="h-4 w-4 text-primary" /> : <Circle className="h-4 w-4 text-muted-foreground" />}
                      {c}
                    </button>
                  </li>
                );
              })}
            </ul>
          </GlassCard>
        </div>

        <div className="flex justify-end">
          <GlowButton disabled={done.size < checks.length || !streaming || evidence.isPending} onClick={confirmScan}>
            {evidence.isPending ? "Saving..." : "Confirm scan"}
          </GlowButton>
        </div>
      </div>
    </AppShell>
  );
}
