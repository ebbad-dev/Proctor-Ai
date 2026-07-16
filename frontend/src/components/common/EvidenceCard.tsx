import { motion } from "framer-motion";
import type { BrowserActivity, EvidenceItem, SessionEvent } from "@/lib/types";
import { GlassCard } from "./GlassCard";
import { Camera, Mic, Image as ImageIcon, IdCard, DoorOpen, ExternalLink, ScanFace } from "lucide-react";
import { useEvidenceLightbox } from "./EvidenceLightbox";
import { NoEvidence } from "./States";

const iconFor: Record<EvidenceItem["type"], React.ReactNode> = {
  screenshot: <ImageIcon className="h-4 w-4" />,
  camera_frame: <Camera className="h-4 w-4" />,
  audio_clip: <Mic className="h-4 w-4" />,
  face: <ScanFace className="h-4 w-4" />,
  id_card: <IdCard className="h-4 w-4" />,
  room_scan: <DoorOpen className="h-4 w-4" />,
};

interface CardProps {
  item: EvidenceItem;
  index?: number;
  items?: EvidenceItem[];
  events?: SessionEvent[];
  browser?: BrowserActivity[];
}

export function EvidenceCard({ item, index = 0, items, events, browser }: CardProps) {
  const { open } = useEvidenceLightbox();
  const handleOpen = () => open({ item, items, events, browser, sessionId: item.session_id });
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.04, duration: 0.35 }}
      whileHover={{ y: -3 }}
    >
      <GlassCard className="overflow-hidden p-0">
        <button
          type="button"
          onClick={handleOpen}
          aria-label={`Open evidence captured at ${new Date(item.timestamp).toLocaleString()}`}
          className="relative block aspect-video w-full bg-black/40 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60"
        >
          <div
            className="absolute inset-0"
            style={{
              background:
                "radial-gradient(60% 60% at 50% 50%, oklch(0.3 0.05 260), oklch(0.12 0.03 260) 80%)",
            }}
          />
          <div className="absolute inset-0 bg-grid opacity-20" />
          <div className="absolute left-2 top-2 flex items-center gap-1.5 rounded bg-black/50 px-2 py-1 text-[11px] backdrop-blur">
            {iconFor[item.type]}
            {item.label ?? item.type}
          </div>
          {item.camera_source && (
            <div className="absolute right-2 top-2 rounded bg-black/50 px-2 py-1 text-[10px] uppercase tracking-wider backdrop-blur">
              {item.camera_source}
            </div>
          )}
        </button>
        <div className="flex items-center justify-between gap-2 p-3 text-xs">
          <span className="text-muted-foreground">{new Date(item.timestamp).toLocaleString()}</span>
          {item.risk_impact != null && (
            <span className="font-mono text-primary">+{item.risk_impact}</span>
          )}
          <button
            onClick={handleOpen}
            aria-label="Inspect evidence"
            className="ml-auto inline-flex items-center gap-1 text-foreground hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60 rounded"
          >
            Inspect <ExternalLink className="h-3 w-3" aria-hidden />
          </button>
        </div>
      </GlassCard>
    </motion.div>
  );
}

interface GalleryProps {
  items: EvidenceItem[];
  events?: SessionEvent[];
  browser?: BrowserActivity[];
}

export function EvidenceGallery({ items, events, browser }: GalleryProps) {
  if (!items.length) return <NoEvidence />;
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {items.map((it, i) => (
        <EvidenceCard
          key={it.id}
          item={it}
          index={i}
          items={items}
          events={events}
          browser={browser}
        />
      ))}
    </div>
  );
}
