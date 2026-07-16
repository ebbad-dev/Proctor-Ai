import { Link } from "@tanstack/react-router";
import type { SessionDetail } from "@/lib/types";
import { StatusBadge } from "./StatusBadge";
import { GlowButton } from "./GlowButton";
import { useSubmitReview } from "@/lib/queries";
import { Check, XCircle, AlertTriangle, Trash2, FileDown, Camera, Globe } from "lucide-react";

export function StickyReviewBar({ session }: { session: SessionDetail }) {
  const review = useSubmitReview(session.id);
  const browserViolations = session.browser_activity.filter((b) => b.risk_impact > 0).length;

  return (
    <div className="sticky bottom-3 z-30 print:hidden">
      <div className="glass shadow-elegant flex flex-wrap items-center gap-2 rounded-2xl px-3 py-2.5 md:px-4">
        <StatusBadge
          label={`Risk ${session.risk_score} · ${session.risk_level}`}
          level={session.risk_level}
        />
        <span className="hidden items-center gap-1.5 rounded-md border border-white/10 bg-white/5 px-2 py-1 text-[11px] text-muted-foreground sm:inline-flex">
          <Camera className="h-3 w-3" /> {session.evidence.length} evidence
        </span>
        <span className="hidden items-center gap-1.5 rounded-md border border-white/10 bg-white/5 px-2 py-1 text-[11px] text-muted-foreground sm:inline-flex">
          <Globe className="h-3 w-3" /> {browserViolations} browser
        </span>

        <div className="ml-auto flex flex-wrap items-center gap-1.5">
          <GlowButton
            size="sm"
            variant="outline"
            onClick={() => review.mutate({ decision: "valid" })}
            aria-label="Mark as valid violation"
          >
            <Check className="h-4 w-4" /> Valid
          </GlowButton>
          <GlowButton
            size="sm"
            variant="ghost"
            onClick={() => review.mutate({ decision: "false_positive" })}
            aria-label="Mark as false positive"
          >
            <XCircle className="h-4 w-4" /> False positive
          </GlowButton>
          <GlowButton
            size="sm"
            variant="ghost"
            onClick={() => review.mutate({ decision: "needs_review" })}
            aria-label="Mark as needs further review"
          >
            <AlertTriangle className="h-4 w-4" /> Review
          </GlowButton>
          <GlowButton
            size="sm"
            variant="ghost"
            onClick={() => review.mutate({ decision: "dismissed" })}
            aria-label="Dismiss"
          >
            <Trash2 className="h-4 w-4" /> Dismiss
          </GlowButton>
          <Link to="/reports" search={{ session_id: session.id }}>
            <GlowButton size="sm" variant="primary" aria-label="Export report">
              <FileDown className="h-4 w-4" /> Export
            </GlowButton>
          </Link>
        </div>
      </div>
    </div>
  );
}
