import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { AppShell } from "@/components/layout/AppShell";
import { GlassCard } from "@/components/common/GlassCard";
import { GlowButton } from "@/components/common/GlowButton";
import { StatusBadge } from "@/components/common/StatusBadge";
import { FloatingOrbs } from "@/components/effects/FloatingOrbs";
import {
  useBrowserGuardActive,
  useCameraStreamHealth,
  useCreateEvidence,
  useExams,
  useHealth,
  useJoinExamByCode,
  useStartAttempt,
} from "@/lib/queries";
import {
  Camera,
  Mic,
  ShieldCheck,
  ScanFace,
  DoorOpen,
  CheckCircle2,
  ArrowRight,
  ArrowLeft,
  Sparkles,
} from "lucide-react";

export const Route = createFileRoute("/setup")({
  head: () => ({
    meta: [
      { title: "Setup Wizard · ProctorAI" },
      {
        name: "description",
        content:
          "Set up your exam session: permissions, cameras, microphone, Browser Guard, ID, and room scan.",
      },
    ],
  }),
  component: SetupPage,
});

const steps = [
  { t: "Welcome", d: "Get ready for your secure exam.", icon: Sparkles },
  { t: "Permissions", d: "Grant camera, microphone, and screen access.", icon: ShieldCheck },
  { t: "Camera Check", d: "Verify your primary camera.", icon: Camera },
  { t: "Microphone Check", d: "Verify your microphone is active.", icon: Mic },
  { t: "Browser Guard", d: "Install and connect the extension.", icon: ShieldCheck },
  { t: "ID Verification", d: "Capture face + ID for verification.", icon: ScanFace },
  { t: "Room Scan", d: "Scan your environment.", icon: DoorOpen },
  { t: "Ready", d: "All checks complete — start your exam.", icon: CheckCircle2 },
];

function SetupPage() {
  const navigate = useNavigate();
  const videoRef = useRef<HTMLVideoElement>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const [i, setI] = useState(0);
  const [selectedExam, setSelectedExam] = useState("");
  const [examCode, setExamCode] = useState("");
  const [rollNumber, setRollNumber] = useState("");
  const [startError, setStartError] = useState("");
  const [starting, setStarting] = useState(false);
  const [cameraPermission, setCameraPermission] = useState<"idle" | "ok" | "error">("idle");
  const [micPermission, setMicPermission] = useState<"idle" | "ok" | "error">("idle");
  const [cameraStreaming, setCameraStreaming] = useState(false);
  const [faceImage, setFaceImage] = useState("");
  const [idImage, setIdImage] = useState("");
  const [roomImage, setRoomImage] = useState("");
  const [roomConfirmed, setRoomConfirmed] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  const health = useHealth();
  const guard = useBrowserGuardActive();
  const primaryCamera = useCameraStreamHealth("primary");
  const exams = useExams();
  const joinCode = useJoinExamByCode();
  const startAttempt = useStartAttempt();
  const evidence = useCreateEvidence();
  const step = steps[i]!;
  const Icon = step.icon;
  const assignedExam = exams.data?.find((item) => item.id === selectedExam) ?? exams.data?.[0];
  const assignedExamRequiresFullscreen = Boolean(
    assignedExam?.rules?.require_fullscreen ?? assignedExam?.rules?.fullscreen_required,
  );

  useEffect(() => {
    if (!selectedExam && exams.data?.[0]?.id) setSelectedExam(exams.data[0].id);
  }, [exams.data, selectedExam]);

  useEffect(() => {
    const updateFullscreen = () => setFullscreen(!!document.fullscreenElement);
    document.addEventListener("fullscreenchange", updateFullscreen);
    updateFullscreen();
    return () => {
      document.removeEventListener("fullscreenchange", updateFullscreen);
      mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
    };
  }, []);

  useEffect(() => {
    if (!videoRef.current || !mediaStreamRef.current) return;
    videoRef.current.srcObject = mediaStreamRef.current;
    videoRef.current.play().catch(() => setCameraStreaming(false));
  }, [cameraStreaming, i]);

  const startCamera = async () => {
    if (!navigator.mediaDevices?.getUserMedia) {
      setCameraPermission("error");
      return;
    }
    try {
      mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
      mediaStreamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setCameraStreaming(true);
      setCameraPermission("ok");
    } catch {
      setCameraStreaming(false);
      setCameraPermission("error");
    }
  };

  const requestMedia = async (kind: "camera" | "microphone") => {
    if (kind === "camera") {
      await startCamera();
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia) {
      setMicPermission("error");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: false,
        audio: true,
      });
      stream.getTracks().forEach((track) => track.stop());
      setMicPermission("ok");
    } catch {
      setMicPermission("error");
    }
  };

  const captureFrame = (kind: "face" | "id" | "room") => {
    const video = videoRef.current;
    if (!video || !cameraStreaming || video.readyState < 2) {
      setStartError("Start the camera and wait for the live preview before capturing evidence.");
      return;
    }
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;
    canvas.getContext("2d")?.drawImage(video, 0, 0, canvas.width, canvas.height);
    const image = canvas.toDataURL("image/jpeg", 0.85);
    if (kind === "face") setFaceImage(image);
    if (kind === "id") setIdImage(image);
    if (kind === "room") setRoomImage(image);
    setStartError("");
  };

  const stepComplete =
    step.t === "Welcome" ||
    (step.t === "Permissions" && cameraPermission === "ok" && micPermission === "ok") ||
    (step.t === "Camera Check" && cameraPermission === "ok" && cameraStreaming) ||
    (step.t === "Microphone Check" && micPermission === "ok") ||
    (step.t === "Browser Guard" && (!assignedExamRequiresFullscreen || fullscreen)) ||
    (step.t === "ID Verification" && !!faceImage && !!idImage) ||
    (step.t === "Room Scan" && !!roomImage && roomConfirmed) ||
    step.t === "Ready";

  const readyToStart =
    !!(selectedExam || exams.data?.[0]?.id || examCode.trim()) &&
    !!rollNumber.trim() &&
    !!faceImage &&
    !!idImage &&
    !!roomImage &&
    roomConfirmed &&
    (!assignedExamRequiresFullscreen || fullscreen);

  const liveBadges = [
    {
      label: health.isSuccess
        ? "Backend online"
        : health.isError
          ? "Backend offline"
          : "Backend checking",
      status: health.isSuccess ? "ok" : health.isError ? "error" : "idle",
    },
    {
      label: primaryCamera.data ? "Camera stream online" : "Camera stream offline",
      status: primaryCamera.data ? "ok" : "warning",
    },
    {
      label: guard.data?.active ? "Browser Guard active" : "Browser Guard inactive",
      status: guard.data?.active ? "ok" : "warning",
    },
  ] as const;

  const startExam = async () => {
    setStartError("");
    if (!selectedExam && !exams.data?.length && !examCode.trim()) {
      setStartError("Select an assigned exam or enter an exam code.");
      return;
    }
    if (!rollNumber.trim()) {
      setStartError("Enter your official university roll number before starting.");
      return;
    }
    setStarting(true);
    try {
      let exam;
      if (examCode.trim()) {
        exam = await joinCode.mutateAsync(examCode.trim());
      } else {
        exam = exams.data?.find((item) => item.id === selectedExam) ?? exams.data?.[0];
      }
      if (!exam) {
        setStartError("Select an assigned exam or join with a valid exam code.");
        return;
      }
      const requiresFullscreen = Boolean(exam.rules?.require_fullscreen ?? exam.rules?.fullscreen_required);
      if (requiresFullscreen && !document.fullscreenElement) {
        setStartError("This exam requires fullscreen. Enter fullscreen before starting.");
        return;
      }
      const session_id =
        `SESSION_${Date.now().toString(36).toUpperCase()}_${Math.random().toString(36).slice(2, 6).toUpperCase()}`;
      const attempt = await startAttempt.mutateAsync({
        exam_id: exam.id,
        roll_number: rollNumber.trim(),
        session_id,
      });
      if (!attempt.session_id) throw new Error("The exam session was created without a monitoring session ID.");
      await evidence.mutateAsync({
        session_id: attempt.session_id,
        evidence_type: "face",
        label: "Pre-exam face capture",
        image_data: faceImage,
      });
      await evidence.mutateAsync({
        session_id: attempt.session_id,
        evidence_type: "id_card",
        label: "Pre-exam university ID capture",
        image_data: idImage,
      });
      await evidence.mutateAsync({
        session_id: attempt.session_id,
        evidence_type: "room_scan",
        label: "Pre-exam room scan confirmation",
        image_data: roomImage,
      });
      mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
      navigate({ to: "/exam", search: { attempt_id: attempt.attempt_id } });
    } catch (exc) {
      setStartError(exc instanceof Error ? exc.message : "Could not start exam session.");
    } finally {
      setStarting(false);
    }
  };

  return (
    <AppShell>
      <div className="relative">
        <FloatingOrbs />
        <div className="relative mx-auto max-w-3xl space-y-4">
          <ol className="grid grid-cols-4 gap-2 md:grid-cols-8">
            {steps.map((s, idx) => (
              <li key={s.t} className="flex flex-col items-center gap-1.5">
                <motion.div
                  animate={{ scale: idx === i ? 1.1 : 1, opacity: idx <= i ? 1 : 0.4 }}
                  className={`grid h-8 w-8 place-items-center rounded-full border ${idx <= i ? "border-primary/60 bg-primary/15 text-primary" : "border-white/10 bg-white/5 text-muted-foreground"}`}
                >
                  {idx < i ? (
                    <CheckCircle2 className="h-4 w-4" />
                  ) : (
                    <span className="text-[11px]">{idx + 1}</span>
                  )}
                </motion.div>
                <div className="hidden text-[10px] uppercase tracking-wider text-muted-foreground md:block">
                  {s.t}
                </div>
              </li>
            ))}
          </ol>

          <motion.div key={i} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
            <GlassCard strong className="p-8 text-center">
              <div className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-gradient-primary text-primary-foreground shadow-glow">
                <Icon className="h-7 w-7" />
              </div>
              <h2 className="mt-4 text-2xl font-bold">{step.t}</h2>
              <p className="mt-2 text-sm text-muted-foreground">{step.d}</p>
              <div className="mt-4 flex flex-wrap justify-center gap-2">
                {liveBadges.map((badge) => (
                  <StatusBadge key={badge.label} label={badge.label} status={badge.status} />
                ))}
              </div>
              {(step.t === "Camera Check" || step.t === "ID Verification" || step.t === "Room Scan") && (
                <div className="mx-auto mt-5 max-w-xl overflow-hidden rounded-xl border border-white/10 bg-black">
                  <video ref={videoRef} className="aspect-video w-full object-cover" muted playsInline />
                  <div className="flex flex-wrap justify-center gap-2 border-t border-white/10 bg-background/90 p-3">
                    <GlowButton variant="outline" size="sm" onClick={startCamera}>
                      <Camera className="h-4 w-4" /> {cameraStreaming ? "Restart camera" : "Start camera"}
                    </GlowButton>
                    {step.t === "ID Verification" && (
                      <>
                        <GlowButton size="sm" disabled={!cameraStreaming} onClick={() => captureFrame("face")}>
                          <ScanFace className="h-4 w-4" /> {faceImage ? "Face captured" : "Capture face"}
                        </GlowButton>
                        <GlowButton size="sm" disabled={!cameraStreaming} onClick={() => captureFrame("id")}>
                          <ShieldCheck className="h-4 w-4" /> {idImage ? "ID captured" : "Capture ID"}
                        </GlowButton>
                      </>
                    )}
                    {step.t === "Room Scan" && (
                      <GlowButton size="sm" disabled={!cameraStreaming} onClick={() => captureFrame("room")}>
                        <DoorOpen className="h-4 w-4" /> {roomImage ? "Room captured" : "Capture room"}
                      </GlowButton>
                    )}
                  </div>
                </div>
              )}
              {step.t === "Room Scan" && (
                <label className="mx-auto mt-3 flex max-w-xl items-start gap-3 rounded-xl border border-white/10 bg-white/[0.03] p-3 text-left text-sm">
                  <input
                    type="checkbox"
                    checked={roomConfirmed}
                    onChange={(event) => setRoomConfirmed(event.target.checked)}
                    className="mt-0.5 h-4 w-4"
                  />
                  <span>I confirm the desk is clear, lighting is adequate, and no unauthorized person, notes, or device is visible.</span>
                </label>
              )}
              {step.t === "Browser Guard" && (
                <div className="mx-auto mt-4 flex max-w-xl flex-col items-center gap-2 rounded-xl border border-white/10 bg-white/[0.03] p-3 text-sm text-muted-foreground">
                  <span>
                    {guard.data?.active
                      ? "Browser Guard exact URL monitoring is connected."
                      : "Fallback tab, focus, clipboard, devtools, and fullscreen monitoring remains available."}
                  </span>
                  {assignedExamRequiresFullscreen && !fullscreen && (
                    <span className="text-amber-200">This exam requires fullscreen before you can continue.</span>
                  )}
                  <GlowButton
                    variant="outline"
                    size="sm"
                    onClick={() => document.documentElement.requestFullscreen?.().catch(() => undefined)}
                  >
                    <ShieldCheck className="h-4 w-4" /> {fullscreen ? "Fullscreen active" : "Enter fullscreen"}
                  </GlowButton>
                </div>
              )}
              {step.t === "Ready" && (
                <div className="mx-auto mt-5 max-w-md text-left">
                  <label className="block text-sm">
                    <span className="mb-1 block text-xs text-muted-foreground">Assigned exam</span>
                    <select
                      value={selectedExam}
                      onChange={(event) => setSelectedExam(event.target.value)}
                      className="h-10 w-full rounded-xl border border-white/10 bg-white/5 px-3 text-sm outline-none"
                    >
                      <option value="" disabled>
                        {exams.isLoading
                          ? "Loading assigned exams..."
                          : exams.data?.length
                            ? "Select an assigned exam"
                            : "No assigned exams"}
                      </option>
                      {(exams.data ?? []).map((exam) => (
                        <option key={exam.id} value={exam.id}>
                          {exam.title}
                        </option>
                      ))}
                    </select>
                  </label>
                  {(!exams.data || exams.data.length === 0) && (
                    <p className="mt-2 rounded-lg border border-amber-400/30 bg-amber-400/10 p-2 text-xs text-amber-200">
                      No assigned exams found for this account. Enter an exam code if your instructor provided one.
                    </p>
                  )}
                  <label className="mt-3 block text-sm">
                    <span className="mb-1 block text-xs text-muted-foreground">Exam code</span>
                    <input
                      value={examCode}
                      onChange={(event) => setExamCode(event.target.value.toUpperCase())}
                      placeholder="WB01"
                      className="h-10 w-full rounded-xl border border-white/10 bg-white/5 px-3 text-sm uppercase outline-none placeholder:text-muted-foreground"
                    />
                  </label>
                  <label className="mt-3 block text-sm">
                    <span className="mb-1 block text-xs text-muted-foreground">Official university roll number</span>
                    <input
                      value={rollNumber}
                      onChange={(event) => setRollNumber(event.target.value)}
                      placeholder="University roll number"
                      className="h-10 w-full rounded-xl border border-white/10 bg-white/5 px-3 text-sm outline-none placeholder:text-muted-foreground"
                    />
                  </label>
                  {startError && (
                    <p className="mt-2 rounded-lg border border-red-400/30 bg-red-400/10 p-2 text-xs text-red-200">
                      {startError}
                    </p>
                  )}
                </div>
              )}
              {(step.t === "Permissions" ||
                step.t === "Camera Check" ||
                step.t === "Microphone Check") && (
                <div className="mt-4 flex flex-wrap justify-center gap-2">
                  <GlowButton variant="outline" size="sm" onClick={() => requestMedia("camera")}>
                    <Camera className="h-4 w-4" /> Camera{" "}
                    {cameraPermission === "ok"
                      ? "allowed"
                      : cameraPermission === "error"
                        ? "blocked"
                        : "test"}
                  </GlowButton>
                  <GlowButton
                    variant="outline"
                    size="sm"
                    onClick={() => requestMedia("microphone")}
                  >
                    <Mic className="h-4 w-4" /> Microphone{" "}
                    {micPermission === "ok"
                      ? "allowed"
                      : micPermission === "error"
                        ? "blocked"
                        : "test"}
                  </GlowButton>
                </div>
              )}
              <div className="mt-6 flex items-center justify-center gap-2">
                <GlowButton
                  variant="ghost"
                  disabled={i === 0}
                  onClick={() => setI((v) => Math.max(0, v - 1))}
                >
                  <ArrowLeft className="h-4 w-4" /> Back
                </GlowButton>
                {i < steps.length - 1 ? (
                  <GlowButton disabled={!stepComplete} onClick={() => setI((v) => Math.min(steps.length - 1, v + 1))}>
                    Continue <ArrowRight className="h-4 w-4" />
                  </GlowButton>
                ) : (
                  <GlowButton onClick={startExam} disabled={starting || evidence.isPending || !readyToStart}>
                    {starting ? "Starting..." : "Start exam"} <ArrowRight className="h-4 w-4" />
                  </GlowButton>
                )}
              </div>
            </GlassCard>
          </motion.div>
        </div>
      </div>
    </AppShell>
  );
}
