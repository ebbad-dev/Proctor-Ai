import { cn } from "@/lib/utils";
import type { RiskLevel } from "@/lib/types";
import { ShieldCheck, AlertTriangle, OctagonAlert, Circle } from "lucide-react";

type Status = "ok" | "warning" | "error" | "info" | "idle";

interface Props {
  label: string;
  status?: Status;
  level?: RiskLevel;
  pulse?: boolean;
  className?: string;
  icon?: React.ReactNode;
}

const statusStyles: Record<Status, string> = {
  ok: "border-emerald-400/30 bg-emerald-400/10 text-emerald-300",
  warning: "border-amber-400/30 bg-amber-400/10 text-amber-300",
  error: "border-red-400/30 bg-red-400/10 text-red-300",
  info: "border-sky-400/30 bg-sky-400/10 text-sky-300",
  idle: "border-white/10 bg-white/5 text-muted-foreground",
};

const riskStyles: Record<RiskLevel, string> = {
  low: "border-emerald-400/30 bg-emerald-400/10 text-emerald-300",
  medium: "border-amber-400/30 bg-amber-400/10 text-amber-300",
  high: "border-orange-400/30 bg-orange-400/10 text-orange-300",
  critical: "border-red-400/30 bg-red-400/10 text-red-300",
};

export function StatusBadge({ label, status, level, pulse, className, icon }: Props) {
  const styles = level ? riskStyles[level] : statusStyles[status ?? "idle"];
  const Icon =
    level === "critical" || status === "error"
      ? OctagonAlert
      : level === "high" || level === "medium" || status === "warning"
        ? AlertTriangle
        : status === "ok" || level === "low"
          ? ShieldCheck
          : Circle;
  return (
    <div
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium",
        styles,
        pulse && "animate-pulse-glow",
        className,
      )}
    >
      <span className="inline-flex h-1.5 w-1.5 rounded-full bg-current" />
      {icon ?? <Icon className="h-3.5 w-3.5" />}
      <span className="leading-none">{label}</span>
    </div>
  );
}
