import type { SystemHealth } from "@/lib/types";
import {
  Camera,
  CameraOff,
  Mic,
  ShieldCheck,
  ShieldOff,
  Database,
  Wifi,
  Server,
} from "lucide-react";
import { GlassCard } from "./GlassCard";
import { cn } from "@/lib/utils";

interface Props {
  health: SystemHealth;
  compact?: boolean;
}

interface Chip {
  label: string;
  detail?: string;
  ok: boolean;
  icon: React.ReactNode;
}

export function HealthStrip({ health, compact }: Props) {
  const chips: Chip[] = [
    {
      label: "Primary Camera",
      detail: health.primary_camera.active
        ? `${health.primary_camera.resolution ?? "—"} · ${health.primary_camera.fps ?? "—"} fps`
        : "Inactive",
      ok: health.primary_camera.active,
      icon: health.primary_camera.active ? <Camera /> : <CameraOff />,
    },
    {
      label: "Secondary Camera",
      detail: health.secondary_camera.active
        ? `${health.secondary_camera.resolution ?? "—"} · ${health.secondary_camera.fps ?? "—"} fps`
        : "Inactive",
      ok: health.secondary_camera.active,
      icon: health.secondary_camera.active ? <Camera /> : <CameraOff />,
    },
    {
      label: "Microphone",
      detail: health.microphone.active ? "Active" : "Muted",
      ok: health.microphone.active,
      icon: <Mic />,
    },
    {
      label: "Browser Guard",
      detail: health.browser_guard.active ? "Active" : "Inactive",
      ok: health.browser_guard.active,
      icon: health.browser_guard.active ? <ShieldCheck /> : <ShieldOff />,
    },
    {
      label: "Backend",
      detail: health.backend.connected ? "Connected" : "Offline",
      ok: health.backend.connected,
      icon: <Server />,
    },
    {
      label: "Database",
      detail: health.database.connected
        ? "Connected"
        : health.database.offline_fallback
          ? "Offline fallback"
          : "Offline",
      ok: health.database.connected,
      icon: <Database />,
    },
    {
      label: "Network",
      detail: `${health.network.latency_ms ?? "—"} ms`,
      ok: health.network.stable,
      icon: <Wifi />,
    },
  ];

  return (
    <GlassCard className={cn("flex flex-wrap items-stretch gap-2 p-2", compact && "p-1.5")}>
      {chips.map((c) => (
        <div
          key={c.label}
          className={cn(
            "flex flex-1 min-w-[150px] items-center gap-2.5 rounded-xl px-3 py-2 transition-colors",
            c.ok ? "bg-emerald-400/5 hover:bg-emerald-400/10" : "bg-red-400/5 hover:bg-red-400/10",
          )}
        >
          <div
            className={cn(
              "grid h-8 w-8 place-items-center rounded-lg [&_svg]:h-4 [&_svg]:w-4",
              c.ok ? "bg-emerald-400/15 text-emerald-300" : "bg-red-400/15 text-red-300",
            )}
          >
            {c.icon}
          </div>
          <div className="min-w-0 leading-tight">
            <div className="truncate text-[11px] uppercase tracking-wider text-muted-foreground">
              {c.label}
            </div>
            <div className="truncate text-xs font-medium text-foreground">{c.detail}</div>
          </div>
          <span
            className={cn(
              "ml-auto h-1.5 w-1.5 rounded-full",
              c.ok ? "bg-emerald-400" : "bg-red-400",
              c.ok && "shadow-[0_0_8px_2px_oklch(0.72_0.18_155_/_0.6)]",
            )}
          />
        </div>
      ))}
    </GlassCard>
  );
}
