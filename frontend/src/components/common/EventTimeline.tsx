import { motion } from "framer-motion";
import type { SessionEvent } from "@/lib/types";
import { cn } from "@/lib/utils";
import {
  Phone,
  UserX,
  Users,
  EyeOff,
  Mic,
  ArrowLeftRight,
  Globe,
  Maximize,
  ShieldCheck,
  Activity,
} from "lucide-react";

const iconFor: Record<SessionEvent["category"], React.ReactNode> = {
  phone_detected: <Phone className="h-4 w-4" />,
  face_missing: <UserX className="h-4 w-4" />,
  multiple_faces: <Users className="h-4 w-4" />,
  gaze_away: <EyeOff className="h-4 w-4" />,
  audio_voice: <Mic className="h-4 w-4" />,
  tab_switch: <ArrowLeftRight className="h-4 w-4" />,
  url_visit: <Globe className="h-4 w-4" />,
  fullscreen_exit: <Maximize className="h-4 w-4" />,
  browser_guard: <ShieldCheck className="h-4 w-4" />,
  system: <Activity className="h-4 w-4" />,
};

const sevStyles = {
  low: "border-emerald-400/30 text-emerald-300 bg-emerald-400/10",
  medium: "border-amber-400/30 text-amber-300 bg-amber-400/10",
  high: "border-orange-400/30 text-orange-300 bg-orange-400/10",
  critical: "border-red-400/30 text-red-300 bg-red-400/10",
};

export function EventTimeline({ events, limit }: { events: SessionEvent[]; limit?: number }) {
  const list = limit ? events.slice(0, limit) : events;
  return (
    <ol className="relative space-y-3 before:absolute before:left-[15px] before:top-2 before:bottom-2 before:w-px before:bg-white/10">
      {list.map((e, i) => (
        <motion.li
          key={e.id}
          initial={{ opacity: 0, x: -8 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: i * 0.04, duration: 0.3 }}
          className="relative flex items-start gap-3 pl-1"
        >
          <div
            className={cn(
              "relative z-10 grid h-8 w-8 shrink-0 place-items-center rounded-full border bg-background/80",
              sevStyles[e.severity],
              e.severity === "critical" && "animate-pulse-glow",
            )}
          >
            {iconFor[e.category]}
          </div>
          <div className="min-w-0 flex-1 rounded-xl border border-white/5 bg-white/[0.03] p-3 hover:bg-white/[0.06] transition-colors">
            <div className="flex items-center justify-between gap-2">
              <span className="truncate text-sm">{e.message}</span>
              {e.risk_impact > 0 && (
                <span className="ml-2 shrink-0 font-mono text-xs text-primary">
                  +{e.risk_impact}
                </span>
              )}
            </div>
            <div className="mt-1 flex items-center gap-3 text-[11px] text-muted-foreground">
              <span>{new Date(e.timestamp).toLocaleTimeString()}</span>
              {e.camera_source && (
                <span className="uppercase tracking-wider">· {e.camera_source}</span>
              )}
              <span
                className={cn(
                  "ml-auto rounded px-1.5 py-0.5 uppercase tracking-wider text-[10px]",
                  sevStyles[e.severity],
                )}
              >
                {e.severity}
              </span>
            </div>
          </div>
        </motion.li>
      ))}
    </ol>
  );
}
