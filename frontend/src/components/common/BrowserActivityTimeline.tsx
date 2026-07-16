import { motion } from "framer-motion";
import type { BrowserActivity } from "@/lib/types";
import { Globe, ArrowLeftRight, Maximize, Clipboard, ClipboardPaste, EyeOff } from "lucide-react";
import { cn } from "@/lib/utils";

const iconFor: Record<BrowserActivity["action"], React.ReactNode> = {
  url_open: <Globe className="h-4 w-4" />,
  tab_switch: <ArrowLeftRight className="h-4 w-4" />,
  fullscreen_exit: <Maximize className="h-4 w-4" />,
  copy: <Clipboard className="h-4 w-4" />,
  paste: <ClipboardPaste className="h-4 w-4" />,
  focus_lost: <EyeOff className="h-4 w-4" />,
};

const catStyles: Record<NonNullable<BrowserActivity["domain_category"]>, string> = {
  ai_assistant: "bg-red-400/10 text-red-300 border-red-400/30",
  suspicious: "bg-red-400/10 text-red-300 border-red-400/30",
  search: "bg-amber-400/10 text-amber-300 border-amber-400/30",
  social: "bg-amber-400/10 text-amber-300 border-amber-400/30",
  education: "bg-emerald-400/10 text-emerald-300 border-emerald-400/30",
  neutral: "bg-white/5 text-muted-foreground border-white/10",
};

export function BrowserActivityTimeline({ items }: { items: BrowserActivity[] }) {
  return (
    <ul className="space-y-2">
      {items.map((a, i) => (
        <motion.li
          key={a.id}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: i * 0.04, duration: 0.3 }}
          className="flex items-start gap-3 rounded-xl border border-white/5 bg-white/[0.03] p-3 hover:bg-white/[0.06] transition-colors"
        >
          <div className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-primary/10 text-primary">
            {iconFor[a.action]}
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center justify-between gap-2">
              <span className="truncate text-sm">
                {a.page_title ?? humanAction(a.action)}
                {a.domain && <span className="text-muted-foreground"> · {a.domain}</span>}
              </span>
              {a.risk_impact > 0 && (
                <span className="ml-2 font-mono text-xs text-primary">+{a.risk_impact}</span>
              )}
            </div>
            <div className="mt-1 flex items-center gap-2 text-[11px] text-muted-foreground">
              <span>{new Date(a.timestamp).toLocaleTimeString()}</span>
              {a.time_away_ms != null && <span>· away {(a.time_away_ms / 1000).toFixed(1)}s</span>}
              {a.domain_category && (
                <span
                  className={cn(
                    "ml-auto rounded border px-1.5 py-0.5 uppercase tracking-wider text-[10px]",
                    catStyles[a.domain_category],
                  )}
                >
                  {a.domain_category.replace("_", " ")}
                </span>
              )}
            </div>
          </div>
        </motion.li>
      ))}
    </ul>
  );
}

function humanAction(a: BrowserActivity["action"]) {
  return (
    {
      url_open: "URL opened",
      tab_switch: "Tab switched",
      fullscreen_exit: "Exited fullscreen",
      copy: "Copy",
      paste: "Paste",
      focus_lost: "Window focus lost",
    } as const
  )[a];
}
