import type { RiskScore, SessionDetail } from "@/lib/types";
import { GlassCard } from "./GlassCard";
import { Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

interface Props {
  risk: RiskScore;
  session?: Pick<SessionDetail, "browser_guard_active" | "id_verification" | "room_scan">;
  compact?: boolean;
  className?: string;
}

/**
 * Deterministic, rule-based risk summary — no LLM.
 * Reads top contributors + session safeguards and renders a concise sentence.
 */
export function RiskStoryCard({ risk, session, compact, className }: Props) {
  const top = [...risk.contributors].sort((a, b) => b.delta - a.delta).slice(0, 3);
  const reasons = top.map((c) => c.label.toLowerCase());
  const levelLabel =
    risk.level === "critical"
      ? "critical-risk"
      : risk.level === "high"
        ? "high-risk"
        : risk.level === "medium"
          ? "medium-risk"
          : "low-risk";

  const verb =
    risk.level === "low" ? "remains a" : risk.level === "medium" ? "is a" : "has been flagged as a";

  const reasonText =
    reasons.length === 0
      ? "no significant signals so far"
      : reasons.length === 1
        ? reasons[0]
        : reasons.length === 2
          ? `${reasons[0]} and ${reasons[1]}`
          : `${reasons[0]}, ${reasons[1]}, and ${reasons[2]}`;

  const safeguards: string[] = [];
  if (session?.browser_guard_active) safeguards.push("Browser Guard active");
  if (session?.id_verification?.verified) safeguards.push("ID verified");
  if (session?.room_scan?.completed) safeguards.push("Room scan completed");

  const tone =
    risk.level === "critical" || risk.level === "high"
      ? "text-red-200"
      : risk.level === "medium"
        ? "text-amber-200"
        : "text-emerald-200";

  return (
    <GlassCard className={cn("p-4", className)}>
      <div className="flex items-start gap-3">
        <div className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-primary/10 text-primary">
          <Sparkles className="h-4 w-4" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold">Risk story</h3>
            <span className={cn("text-[11px] uppercase tracking-wider", tone)}>{levelLabel}</span>
          </div>
          <p
            className={cn(
              "mt-1 text-sm leading-relaxed text-foreground/90",
              compact && "text-[13px]",
            )}
          >
            This session {verb} <span className={cn("font-medium", tone)}>{levelLabel}</span>{" "}
            session
            {reasons.length > 0 ? (
              <>
                {" "}
                mainly due to <span className="text-foreground">{reasonText}</span>
              </>
            ) : (
              ` — ${reasonText}`
            )}
            .
            {safeguards.length > 0 && !compact && (
              <>
                {" "}
                Safeguards in place:{" "}
                <span className="text-foreground">{safeguards.join(", ")}</span>.
              </>
            )}
          </p>
          {!compact && (
            <p className="mt-2 text-[11px] text-muted-foreground">
              Summary generated from risk contributors. Instructor decision required for final
              outcome.
            </p>
          )}
        </div>
      </div>
    </GlassCard>
  );
}
