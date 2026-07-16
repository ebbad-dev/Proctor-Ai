import { useState } from "react";
import { AlertTriangle, Camera, CameraOff } from "lucide-react";
import { GlassCard } from "./GlassCard";
import { ScanLineOverlay } from "@/components/effects/ScanLineOverlay";
import { cn } from "@/lib/utils";

interface Props {
  label: string;
  source?: "primary" | "secondary";
  active: boolean;
  fps?: number;
  resolution?: string;
  streamUrl?: string | null;
  className?: string;
}

export function CameraFeedCard({
  label,
  source = "primary",
  active,
  fps,
  resolution,
  streamUrl,
  className,
}: Props) {
  const [errored, setErrored] = useState(false);
  const showStream = active && !!streamUrl && !errored;

  return (
    <GlassCard className={cn("relative overflow-hidden p-0", className)}>
      <div className="relative aspect-video w-full bg-black/60">
        {showStream && (
          <img
            src={streamUrl}
            alt={`${label} live feed`}
            onError={() => setErrored(true)}
            className="absolute inset-0 h-full w-full object-cover"
          />
        )}

        {!showStream && (
          <div className="absolute inset-0 grid place-items-center text-muted-foreground">
            <div className="flex flex-col items-center gap-2 text-xs">
              {errored ? (
                <AlertTriangle className="h-6 w-6 text-amber-300" />
              ) : (
                <CameraOff className="h-6 w-6" />
              )}
              <span>{errored ? "Stream error" : active ? "Camera stream unavailable" : "Camera inactive"}</span>
            </div>
          </div>
        )}

        {showStream && <ScanLineOverlay />}

        <div className="absolute inset-x-0 top-0 flex items-center justify-between p-3 text-xs">
          <div className="flex items-center gap-2 rounded-md bg-black/40 px-2 py-1 backdrop-blur">
            <Camera className="h-3.5 w-3.5 text-primary" />
            <span className="font-medium">{label}</span>
            <span className="text-muted-foreground">- {source}</span>
          </div>
          <div className="flex items-center gap-2">
            {showStream && (
              <span className="flex items-center gap-1.5 rounded-md bg-black/40 px-2 py-1 backdrop-blur">
                <span className="h-1.5 w-1.5 rounded-full bg-red-400 shadow-[0_0_8px_2px_rgba(248,113,113,0.7)]" />
                LIVE
              </span>
            )}
            {fps != null && (
              <span className="rounded-md bg-black/40 px-2 py-1 text-muted-foreground backdrop-blur">
                {fps} fps
              </span>
            )}
          </div>
        </div>

        {resolution && (
          <div className="absolute inset-x-0 bottom-0 flex items-center justify-between p-3 text-[10px] uppercase text-muted-foreground">
            <span>{resolution}</span>
            <span>
              ProctorAI -{" "}
              {new Date().toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit",
                second: "2-digit",
              })}
            </span>
          </div>
        )}
      </div>
    </GlassCard>
  );
}
