import { useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type { EvidenceItem, RiskLevel, SessionEvent } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Eye, Globe, Mic, Activity, Camera, Filter, ChevronDown } from "lucide-react";

type Lane = "vision" | "browser" | "audio" | "system" | "evidence";

const laneConfig: Record<
  Lane,
  { label: string; icon: React.ReactNode; ring: string; tint: string }
> = {
  vision: {
    label: "Vision",
    icon: <Eye className="h-3.5 w-3.5" />,
    ring: "border-cyan-400/30 text-cyan-200",
    tint: "bg-cyan-400/10",
  },
  browser: {
    label: "Browser",
    icon: <Globe className="h-3.5 w-3.5" />,
    ring: "border-violet-400/30 text-violet-200",
    tint: "bg-violet-400/10",
  },
  audio: {
    label: "Audio",
    icon: <Mic className="h-3.5 w-3.5" />,
    ring: "border-amber-400/30 text-amber-200",
    tint: "bg-amber-400/10",
  },
  system: {
    label: "System",
    icon: <Activity className="h-3.5 w-3.5" />,
    ring: "border-white/20 text-muted-foreground",
    tint: "bg-white/5",
  },
  evidence: {
    label: "Evidence",
    icon: <Camera className="h-3.5 w-3.5" />,
    ring: "border-emerald-400/30 text-emerald-200",
    tint: "bg-emerald-400/10",
  },
};

const sevDot: Record<RiskLevel, string> = {
  low: "bg-emerald-400",
  medium: "bg-amber-400",
  high: "bg-orange-400",
  critical: "bg-red-400",
};

function laneFor(cat: SessionEvent["category"]): Lane {
  if (
    cat === "phone_detected" ||
    cat === "face_missing" ||
    cat === "multiple_faces" ||
    cat === "gaze_away"
  )
    return "vision";
  if (
    cat === "tab_switch" ||
    cat === "url_visit" ||
    cat === "fullscreen_exit" ||
    cat === "browser_guard"
  )
    return "browser";
  if (cat === "audio_voice") return "audio";
  return "system";
}

interface Props {
  events: SessionEvent[];
  evidence?: EvidenceItem[];
}

export function LaneEventTimeline({ events, evidence = [] }: Props) {
  const [showFilters, setShowFilters] = useState(false);
  const [lanesOn, setLanesOn] = useState<Record<Lane, boolean>>({
    vision: true,
    browser: true,
    audio: true,
    system: true,
    evidence: true,
  });
  const [sevOn, setSevOn] = useState<Record<RiskLevel, boolean>>({
    low: true,
    medium: true,
    high: true,
    critical: true,
  });

  const itemsByLane = useMemo(() => {
    const acc: Record<
      Lane,
      Array<{ id: string; ts: number; label: string; severity: RiskLevel; impact?: number }>
    > = {
      vision: [],
      browser: [],
      audio: [],
      system: [],
      evidence: [],
    };
    for (const e of events) {
      const lane = laneFor(e.category);
      if (!lanesOn[lane] || !sevOn[e.severity]) continue;
      acc[lane].push({
        id: e.id,
        ts: new Date(e.timestamp).getTime(),
        label: e.message,
        severity: e.severity,
        impact: e.risk_impact,
      });
    }
    if (lanesOn.evidence) {
      for (const v of evidence) {
        acc.evidence.push({
          id: v.id,
          ts: new Date(v.timestamp).getTime(),
          label: v.label ?? v.type.replace("_", " "),
          severity: "medium",
          impact: v.risk_impact,
        });
      }
    }
    return acc;
  }, [events, evidence, lanesOn, sevOn]);

  const allTs = useMemo(() => {
    const xs = Object.values(itemsByLane)
      .flat()
      .map((i) => i.ts);
    if (xs.length === 0) return { min: 0, max: 1 };
    return { min: Math.min(...xs), max: Math.max(...xs) };
  }, [itemsByLane]);

  const pct = (ts: number) => {
    const range = Math.max(1, allTs.max - allTs.min);
    return ((ts - allTs.min) / range) * 100;
  };

  const lanes: Lane[] = ["vision", "browser", "audio", "system", "evidence"];

  return (
    <div className="space-y-3">
      {/* Filter bar — progressive disclosure */}
      <div className="rounded-xl border border-white/5 bg-white/[0.03]">
        <button
          onClick={() => setShowFilters((v) => !v)}
          aria-expanded={showFilters}
          className="flex w-full items-center gap-2 px-3 py-2 text-xs text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50"
        >
          <Filter className="h-3.5 w-3.5" /> Filters
          <span className="ml-1 text-[11px]">
            {Object.values(lanesOn).filter(Boolean).length}/5 lanes ·{" "}
            {Object.values(sevOn).filter(Boolean).length}/4 severities
          </span>
          <ChevronDown
            className={cn("ml-auto h-3.5 w-3.5 transition-transform", showFilters && "rotate-180")}
          />
        </button>
        <AnimatePresence initial={false}>
          {showFilters && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="overflow-hidden border-t border-white/5"
            >
              <div className="flex flex-wrap items-center gap-2 p-3">
                {lanes.map((l) => (
                  <button
                    key={l}
                    onClick={() => setLanesOn((s) => ({ ...s, [l]: !s[l] }))}
                    className={cn(
                      "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] transition",
                      lanesOn[l]
                        ? laneConfig[l].ring + " " + laneConfig[l].tint
                        : "border-white/10 text-muted-foreground opacity-50 hover:opacity-100",
                    )}
                  >
                    {laneConfig[l].icon} {laneConfig[l].label}
                  </button>
                ))}
                <div className="mx-2 h-5 w-px bg-white/10" />
                {(["low", "medium", "high", "critical"] as RiskLevel[]).map((sv) => (
                  <button
                    key={sv}
                    onClick={() => setSevOn((s) => ({ ...s, [sv]: !s[sv] }))}
                    className={cn(
                      "inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-[11px] uppercase tracking-wider transition",
                      !sevOn[sv] && "opacity-40",
                    )}
                  >
                    <span className={cn("h-1.5 w-1.5 rounded-full", sevDot[sv])} /> {sv}
                  </button>
                ))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Lanes */}
      <div className="space-y-2">
        {lanes.map((l) => {
          const items = itemsByLane[l];
          return (
            <div key={l} className="flex items-stretch gap-3">
              <div
                className={cn(
                  "flex w-28 shrink-0 items-center gap-2 rounded-lg border px-2.5 py-2 text-[11px]",
                  laneConfig[l].ring,
                  laneConfig[l].tint,
                )}
              >
                {laneConfig[l].icon} {laneConfig[l].label}
                <span className="ml-auto opacity-70">{items.length}</span>
              </div>
              <div className="relative flex-1 overflow-hidden rounded-lg border border-white/5 bg-white/[0.02]">
                <div className="absolute inset-y-1/2 left-2 right-2 h-px bg-white/10" />
                {items.length === 0 ? (
                  <div className="grid h-12 place-items-center text-[11px] text-muted-foreground/70">
                    No events
                  </div>
                ) : (
                  <div className="relative h-12">
                    {items.map((it) => (
                      <div
                        key={it.id}
                        title={`${it.label} · ${new Date(it.ts).toLocaleTimeString()}${it.impact ? ` · +${it.impact}` : ""}`}
                        className={cn(
                          "group absolute top-1/2 -translate-x-1/2 -translate-y-1/2 cursor-default rounded-full ring-2 ring-background transition hover:scale-125",
                          sevDot[it.severity],
                        )}
                        style={{ left: `${pct(it.ts)}%`, width: 10, height: 10 }}
                      />
                    ))}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
