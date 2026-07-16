import { motion } from "framer-motion";
import type { RiskContributor } from "@/lib/types";
import { Phone, User, Eye, Mic, Globe, Activity, IdCard, DoorOpen, Sparkles } from "lucide-react";

const iconFor: Record<RiskContributor["category"], React.ReactNode> = {
  phone: <Phone className="h-4 w-4" />,
  face: <User className="h-4 w-4" />,
  gaze: <Eye className="h-4 w-4" />,
  audio: <Mic className="h-4 w-4" />,
  browser: <Globe className="h-4 w-4" />,
  pattern: <Activity className="h-4 w-4" />,
  id: <IdCard className="h-4 w-4" />,
  room: <DoorOpen className="h-4 w-4" />,
  other: <Sparkles className="h-4 w-4" />,
};

export function RiskContributorList({ items }: { items: RiskContributor[] }) {
  const max = Math.max(...items.map((i) => i.delta), 1);
  return (
    <ul className="space-y-2">
      {items.map((c, i) => (
        <motion.li
          key={c.id}
          initial={{ opacity: 0, x: -10 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: i * 0.05, duration: 0.3 }}
          className="group flex items-center gap-3 rounded-xl border border-white/5 bg-white/[0.03] p-2.5 hover:bg-white/[0.06] transition-colors"
        >
          <div className="grid h-8 w-8 place-items-center rounded-lg bg-primary/10 text-primary">
            {iconFor[c.category]}
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center justify-between gap-2 text-sm">
              <span className="truncate">{c.label}</span>
              <span className="font-mono text-primary">+{c.delta}</span>
            </div>
            <div className="mt-1 h-1 overflow-hidden rounded-full bg-white/5">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${(c.delta / max) * 100}%` }}
                transition={{ duration: 0.8, delay: i * 0.05 }}
                className="h-full bg-gradient-primary"
              />
            </div>
          </div>
        </motion.li>
      ))}
    </ul>
  );
}
