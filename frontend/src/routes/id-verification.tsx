import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { GlassCard } from "@/components/common/GlassCard";
import { GlowButton } from "@/components/common/GlowButton";
import { StatusBadge } from "@/components/common/StatusBadge";
import { useCreateEvidence, useSessions } from "@/lib/queries";
import { Camera, IdCard, ShieldCheck } from "lucide-react";

export const Route = createFileRoute("/id-verification")({
  head: () => ({
    meta: [
      { title: "ID Verification - ProctorAI" },
      { name: "description", content: "Capture your face and ID evidence for verification." },
    ],
  }),
  component: IdVerificationPage,
});

function IdVerificationPage() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
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

  const capture = async (type: "face" | "id_card") => {
    setMessage("");
    setMessageKind("idle");
    if (!sessionId) {
      setMessage("No exam session is available. Complete exam setup first.");
      setMessageKind("error");
      return;
    }
    if (!videoRef.current || !streaming || videoRef.current.readyState < 2) {
      setMessage("Start a session and camera before capturing evidence.");
      setMessageKind("error");
      return;
    }
    const canvas = document.createElement("canvas");
    canvas.width = videoRef.current.videoWidth || 640;
    canvas.height = videoRef.current.videoHeight || 480;
    canvas.getContext("2d")?.drawImage(videoRef.current, 0, 0, canvas.width, canvas.height);
    const image_data = canvas.toDataURL("image/jpeg", 0.85);
    try {
      await evidence.mutateAsync({
        session_id: sessionId,
        evidence_type: type,
        label: type === "face" ? "Face capture" : "ID card capture",
        image_data,
      });
      setMessage(`${type === "face" ? "Face" : "ID card"} evidence saved.`);
      setMessageKind("success");
    } catch (exc) {
      setMessage(exc instanceof Error ? exc.message : "Could not save identity evidence.");
      setMessageKind("error");
    }
  };

  return (
    <AppShell>
      <div className="mx-auto max-w-5xl space-y-4">
        <GlassCard className="p-5">
          <h1 className="text-lg font-semibold">ID verification</h1>
          <p className="text-xs text-muted-foreground">
            Captures are stored as evidence for the active exam session.
          </p>
        </GlassCard>

        <GlassCard className="overflow-hidden p-0">
          <video ref={videoRef} className="aspect-video w-full bg-black object-cover" muted playsInline />
          <div className="flex flex-wrap items-center gap-3 p-4">
            <GlowButton variant="outline" onClick={startCamera}>
              <Camera className="h-4 w-4" /> {streaming ? "Camera active" : "Start camera"}
            </GlowButton>
            <GlowButton disabled={!streaming || evidence.isPending} onClick={() => capture("face")}>
              <Camera className="h-4 w-4" /> Capture face
            </GlowButton>
            <GlowButton disabled={!streaming || evidence.isPending} onClick={() => capture("id_card")}>
              <IdCard className="h-4 w-4" /> Capture ID
            </GlowButton>
          </div>
        </GlassCard>

        <GlassCard className="flex flex-wrap items-center gap-3 p-4">
          <ShieldCheck className="h-5 w-5 text-primary" />
          <div className="text-sm">Verification status</div>
          <StatusBadge
            label={messageKind === "success" ? "Evidence saved" : messageKind === "error" ? "Action required" : "Pending capture"}
            status={messageKind === "success" ? "ok" : messageKind === "error" ? "error" : "warning"}
          />
          {message && <span className={messageKind === "error" ? "text-sm text-red-200" : "text-sm text-muted-foreground"}>{message}</span>}
        </GlassCard>
      </div>
    </AppShell>
  );
}
