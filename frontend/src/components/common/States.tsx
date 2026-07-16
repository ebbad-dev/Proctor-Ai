import { Link } from "@tanstack/react-router";
import { Skeleton } from "@/components/ui/skeleton";
import { GlassCard } from "./GlassCard";
import { GlowButton } from "./GlowButton";
import { AlertTriangle, Inbox, Camera, Globe, Users, ShieldOff, Mic, FileText } from "lucide-react";

export function LoadingSkeleton({
  lines = 3,
  className = "",
}: {
  lines?: number;
  className?: string;
}) {
  return (
    <div className={`space-y-2 ${className}`}>
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton key={i} className="h-10 w-full" />
      ))}
    </div>
  );
}

export function EmptyState({
  title,
  description,
  icon,
  action,
}: {
  title: string;
  description?: string;
  icon?: React.ReactNode;
  action?: { label: string; to: string };
}) {
  return (
    <GlassCard className="grid place-items-center p-10 text-center">
      <div className="grid h-12 w-12 place-items-center rounded-2xl bg-primary/10 text-primary">
        {icon ?? <Inbox className="h-6 w-6" aria-hidden />}
      </div>
      <h3 className="mt-3 text-base font-semibold">{title}</h3>
      {description && <p className="mt-1 max-w-sm text-sm text-muted-foreground">{description}</p>}
      {action && (
        <Link to={action.to} className="mt-4 inline-block">
          <GlowButton size="sm" variant="outline">
            {action.label}
          </GlowButton>
        </Link>
      )}
    </GlassCard>
  );
}

export function ErrorBanner({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div
      role="alert"
      className="flex items-center gap-3 rounded-xl border border-red-400/30 bg-red-400/10 p-3 text-sm text-red-200"
    >
      <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden />
      <span className="flex-1">{message}</span>
      {onRetry && (
        <button
          onClick={onRetry}
          className="rounded-md border border-red-400/30 px-2 py-1 text-xs hover:bg-red-400/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60"
        >
          Retry
        </button>
      )}
    </div>
  );
}

/* ---------- Polished presets ---------- */

export const NoEvidence = () => (
  <EmptyState
    icon={<Camera className="h-6 w-6" aria-hidden />}
    title="No evidence captured yet"
    description="Evidence is automatically captured when the proctoring engine detects a suspicious event. Nothing to review right now."
  />
);

export const NoBrowserActivity = () => (
  <EmptyState
    icon={<Globe className="h-6 w-6" aria-hidden />}
    title="No browser activity recorded"
    description="The student has not switched tabs, exited fullscreen, or visited restricted URLs during this session."
  />
);

export const NoSessions = () => (
  <EmptyState
    icon={<Users className="h-6 w-6" aria-hidden />}
    title="No proctoring sessions"
    description="There are no sessions matching your filters. Start a new exam from the Setup Wizard."
    action={{ label: "Open Setup Wizard", to: "/setup" }}
  />
);

export const BrowserGuardInactive = () => (
  <EmptyState
    icon={<ShieldOff className="h-6 w-6" aria-hidden />}
    title="Browser Guard is not active"
    description="Install the Browser Guard extension to enable precise tab and URL tracking. Without it, only basic tab-switch detection is available."
    action={{ label: "Open Browser Guard", to: "/browser-guard" }}
  />
);

export const NoAudioEvents = () => (
  <EmptyState
    icon={<Mic className="h-6 w-6" aria-hidden />}
    title="No audio events"
    description="The microphone is active but has not detected voices, multiple speakers, or unusual background noise."
  />
);

export const NoReports = () => (
  <EmptyState
    icon={<FileText className="h-6 w-6" aria-hidden />}
    title="No reports generated"
    description="Generate a report from any reviewed session. Reports include risk analysis, evidence, and instructor decisions."
    action={{ label: "Open Instructor Dashboard", to: "/instructor" }}
  />
);
