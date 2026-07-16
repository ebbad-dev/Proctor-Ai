import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { Dialog, DialogContent, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import type { BrowserActivity, EvidenceItem, SessionEvent } from "@/lib/types";
import {
  Camera,
  Mic,
  Image as ImageIcon,
  IdCard,
  DoorOpen,
  ScanFace,
  Check,
  XCircle,
  AlertTriangle,
  Trash2,
  ChevronLeft,
  ChevronRight,
  ZoomIn,
  ZoomOut,
  Download,
  RotateCcw,
} from "lucide-react";
import { GlowButton } from "./GlowButton";
import { useSubmitReview } from "@/lib/queries";
import { EventTimeline } from "./EventTimeline";
import { BrowserActivityTimeline } from "./BrowserActivityTimeline";
import { authHeaders } from "@/lib/auth";

interface OpenArgs {
  item: EvidenceItem;
  items?: EvidenceItem[];
  events?: SessionEvent[];
  browser?: BrowserActivity[];
  sessionId?: string;
}

interface Ctx {
  open: (args: OpenArgs) => void;
  close: () => void;
}

const LightboxContext = createContext<Ctx | null>(null);

export function useEvidenceLightbox() {
  const ctx = useContext(LightboxContext);
  if (!ctx) throw new Error("useEvidenceLightbox must be used within EvidenceLightboxProvider");
  return ctx;
}

const iconFor: Record<EvidenceItem["type"], React.ReactNode> = {
  screenshot: <ImageIcon className="h-4 w-4" />,
  camera_frame: <Camera className="h-4 w-4" />,
  audio_clip: <Mic className="h-4 w-4" />,
  face: <ScanFace className="h-4 w-4" />,
  id_card: <IdCard className="h-4 w-4" />,
  room_scan: <DoorOpen className="h-4 w-4" />,
};

const bigIconFor: Record<EvidenceItem["type"], React.ReactNode> = {
  screenshot: <ImageIcon className="h-10 w-10 opacity-40" />,
  camera_frame: <Camera className="h-10 w-10 opacity-40" />,
  audio_clip: <Mic className="h-10 w-10 opacity-40" />,
  face: <ScanFace className="h-10 w-10 opacity-40" />,
  id_card: <IdCard className="h-10 w-10 opacity-40" />,
  room_scan: <DoorOpen className="h-10 w-10 opacity-40" />,
};

export function EvidenceLightboxProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<OpenArgs | null>(null);
  const [index, setIndex] = useState(0);
  const [notes, setNotes] = useState("");

  const open = useCallback((args: OpenArgs) => {
    setState(args);
    const list = args.items ?? [args.item];
    setIndex(
      Math.max(
        0,
        list.findIndex((e) => e.id === args.item.id),
      ),
    );
    setNotes("");
  }, []);
  const close = useCallback(() => setState(null), []);

  const ctx = useMemo(() => ({ open, close }), [open, close]);

  return (
    <LightboxContext.Provider value={ctx}>
      {children}
      <LightboxView
        state={state}
        index={index}
        setIndex={setIndex}
        notes={notes}
        setNotes={setNotes}
        onClose={close}
      />
    </LightboxContext.Provider>
  );
}

function LightboxView({
  state,
  index,
  setIndex,
  notes,
  setNotes,
  onClose,
}: {
  state: OpenArgs | null;
  index: number;
  setIndex: (i: number) => void;
  notes: string;
  setNotes: (n: string) => void;
  onClose: () => void;
}) {
  const items = state?.items ?? (state ? [state.item] : []);
  const current = items[index] ?? state?.item;
  const sessionId = state?.sessionId ?? current?.session_id ?? "";
  const review = useSubmitReview(sessionId);
  const sourceImageUrl = current?.full_url || current?.thumbnail_url || "";
  const [imageUrl, setImageUrl] = useState("");

  // --- Zoom / pan state ---
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const dragStart = useRef({ x: 0, y: 0, panX: 0, panY: 0 });
  const heroRef = useRef<HTMLDivElement>(null);

  const hasImage = !!imageUrl;
  const isZoomed = zoom > 1;

  const resetZoom = useCallback(() => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  }, []);

  const clampPan = useCallback((nextPan: { x: number; y: number }, nextZoom: number) => {
    if (!heroRef.current || nextZoom <= 1) return { x: 0, y: 0 };
    const rect = heroRef.current.getBoundingClientRect();
    const maxX = (rect.width * (nextZoom - 1)) / 2;
    const maxY = (rect.height * (nextZoom - 1)) / 2;
    return {
      x: Math.max(-maxX, Math.min(maxX, nextPan.x)),
      y: Math.max(-maxY, Math.min(maxY, nextPan.y)),
    };
  }, []);

  const applyZoom = useCallback(
    (delta: number) => {
      setZoom((prev) => {
        const next = Math.max(1, Math.min(5, +(prev + delta).toFixed(2)));
        setPan((p) => clampPan(p, next));
        return next;
      });
    },
    [clampPan],
  );

  // Reset zoom when item changes
  useEffect(() => {
    resetZoom();
  }, [index, resetZoom]);

  useEffect(() => {
    const controller = new AbortController();
    let objectUrl = "";
    setImageUrl("");
    if (!sourceImageUrl) return () => controller.abort();
    void fetch(sourceImageUrl, { headers: authHeaders(), signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error(`Evidence fetch failed (${response.status})`);
        return response.blob();
      })
      .then((blob) => {
        objectUrl = URL.createObjectURL(blob);
        setImageUrl(objectUrl);
      })
      .catch(() => undefined);
    return () => {
      controller.abort();
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [sourceImageUrl]);

  // Keyboard shortcuts
  useEffect(() => {
    if (!state) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "ArrowLeft") {
        e.preventDefault();
        setIndex(Math.max(0, index - 1));
      }
      if (e.key === "ArrowRight") {
        e.preventDefault();
        setIndex(Math.min(items.length - 1, index + 1));
      }
      if (e.key === "+" || e.key === "=") {
        e.preventDefault();
        applyZoom(0.5);
      }
      if (e.key === "-" || e.key === "_") {
        e.preventDefault();
        applyZoom(-0.5);
      }
      if (e.key === "0") {
        e.preventDefault();
        resetZoom();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [state, index, items.length, setIndex, applyZoom, resetZoom]);

  const ts = current ? new Date(current.timestamp).getTime() : 0;
  const window_ms = 30_000;
  const relatedEvents = useMemo(
    () =>
      (state?.events ?? []).filter(
        (e) => Math.abs(new Date(e.timestamp).getTime() - ts) <= window_ms,
      ),
    [state?.events, ts],
  );
  const relatedBrowser = useMemo(
    () =>
      (state?.browser ?? []).filter(
        (b) => Math.abs(new Date(b.timestamp).getTime() - ts) <= window_ms,
      ),
    [state?.browser, ts],
  );

  if (!current) return null;

  const decide = (d: "valid" | "false_positive" | "needs_review" | "dismissed") => {
    review.mutate({ decision: d, notes });
    onClose();
  };

  const handleWheel = (e: React.WheelEvent) => {
    if (!hasImage) return;
    e.preventDefault();
    const delta = e.deltaY > 0 ? -0.25 : 0.25;
    applyZoom(delta);
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    if (!hasImage || !isZoomed) return;
    setIsDragging(true);
    dragStart.current = {
      x: e.clientX,
      y: e.clientY,
      panX: pan.x,
      panY: pan.y,
    };
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging || !heroRef.current) return;
    const dx = e.clientX - dragStart.current.x;
    const dy = e.clientY - dragStart.current.y;
    const nextPan = {
      x: dragStart.current.panX + dx,
      y: dragStart.current.panY + dy,
    };
    setPan(clampPan(nextPan, zoom));
  };

  const handleMouseUp = () => setIsDragging(false);

  const handleClick = (e: React.MouseEvent) => {
    if (isDragging) return;
    if (!hasImage) return;
    // Toggle zoom if not dragging
    if (zoom <= 1) {
      setZoom(2.5);
    } else {
      resetZoom();
    }
  };

  return (
    <Dialog open={!!state} onOpenChange={(o: boolean) => !o && onClose()}>
      <DialogContent className="max-h-[92vh] max-w-5xl overflow-hidden p-0">
        <DialogTitle className="sr-only">Evidence inspector</DialogTitle>
        <DialogDescription className="sr-only">
          Detailed evidence view with related events and decision controls.
        </DialogDescription>
        <div className="grid grid-cols-1 md:grid-cols-[1.4fr,1fr]">
          {/* Hero */}
          <div
            ref={heroRef}
            className="relative aspect-video w-full overflow-hidden bg-black/60 md:aspect-auto md:h-[92vh] md:max-h-[640px]"
            onWheel={handleWheel}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseUp}
            onClick={handleClick}
            style={{
              cursor: isZoomed
                ? isDragging
                  ? "grabbing"
                  : "grab"
                : hasImage
                  ? "zoom-in"
                  : "default",
            }}
          >
            {/* Background fallback always visible behind image */}
            <div
              className="absolute inset-0"
              style={{
                background:
                  "radial-gradient(60% 60% at 50% 50%, oklch(0.3 0.05 260), oklch(0.10 0.03 260) 80%)",
              }}
            />
            <div className="absolute inset-0 bg-grid opacity-20" />

            {/* Evidence image */}
            {hasImage ? (
              <img
                src={imageUrl}
                alt={`${current.label ?? current.type} evidence`}
                className="pointer-events-none absolute inset-0 h-full w-full object-contain transition-transform duration-200 ease-out will-change-transform"
                style={{
                  transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
                }}
                draggable={false}
              />
            ) : (
              <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center gap-3">
                {bigIconFor[current.type]}
                <span className="text-sm text-muted-foreground">
                  {current.label ?? current.type}
                </span>
              </div>
            )}

            {/* Top-left type badge */}
            <div className="absolute left-3 top-3 inline-flex items-center gap-1.5 rounded bg-black/60 px-2 py-1 text-xs backdrop-blur">
              {iconFor[current.type]} {current.label ?? current.type}
            </div>

            {/* Top-right camera source */}
            {current.camera_source && (
              <div className="absolute right-3 top-3 rounded bg-black/60 px-2 py-1 text-[10px] uppercase tracking-wider backdrop-blur">
                {current.camera_source}
              </div>
            )}

            {/* Navigation arrows */}
            {items.length > 1 && (
              <>
                <button
                  aria-label="Previous evidence"
                  onClick={(e) => {
                    e.stopPropagation();
                    setIndex(Math.max(0, index - 1));
                  }}
                  disabled={index === 0}
                  className="absolute left-2 top-1/2 grid h-10 w-10 -translate-y-1/2 place-items-center rounded-full bg-black/60 text-white backdrop-blur transition hover:bg-black/80 disabled:opacity-30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                >
                  <ChevronLeft className="h-5 w-5" />
                </button>
                <button
                  aria-label="Next evidence"
                  onClick={(e) => {
                    e.stopPropagation();
                    setIndex(Math.min(items.length - 1, index + 1));
                  }}
                  disabled={index === items.length - 1}
                  className="absolute right-2 top-1/2 grid h-10 w-10 -translate-y-1/2 place-items-center rounded-full bg-black/60 text-white backdrop-blur transition hover:bg-black/80 disabled:opacity-30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                >
                  <ChevronRight className="h-5 w-5" />
                </button>
                <div className="absolute bottom-12 left-1/2 -translate-x-1/2 rounded bg-black/60 px-2 py-1 text-[11px] backdrop-blur">
                  {index + 1} / {items.length}
                </div>
              </>
            )}

            {/* Zoom / download toolbar */}
            <div className="absolute bottom-3 left-1/2 flex -translate-x-1/2 items-center gap-1 rounded-full bg-black/70 px-2 py-1 backdrop-blur">
              <ToolbarButton
                aria-label="Zoom out"
                disabled={zoom <= 1}
                onClick={(e) => {
                  e.stopPropagation();
                  applyZoom(-0.5);
                }}
              >
                <ZoomOut className="h-4 w-4" />
              </ToolbarButton>
              <span className="min-w-[3ch] px-1 text-center text-[11px] tabular-nums text-white/80">
                {Math.round(zoom * 100)}%
              </span>
              <ToolbarButton
                aria-label="Zoom in"
                disabled={zoom >= 5}
                onClick={(e) => {
                  e.stopPropagation();
                  applyZoom(0.5);
                }}
              >
                <ZoomIn className="h-4 w-4" />
              </ToolbarButton>
              <div className="mx-1 h-4 w-px bg-white/20" />
              <ToolbarButton
                aria-label="Reset zoom"
                disabled={zoom === 1}
                onClick={(e) => {
                  e.stopPropagation();
                  resetZoom();
                }}
              >
                <RotateCcw className="h-4 w-4" />
              </ToolbarButton>
              <a
                href={imageUrl}
                download={`evidence-${current.id}-${current.type}.png`}
                aria-label="Download evidence"
                className="grid h-8 w-8 place-items-center rounded-full text-white/80 transition hover:bg-white/20 hover:text-white disabled:pointer-events-none disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                onClick={(e) => {
                  if (!imageUrl) {
                    e.preventDefault();
                  } else {
                    e.stopPropagation();
                  }
                }}
                style={{ pointerEvents: imageUrl ? "auto" : "none", opacity: imageUrl ? 1 : 0.4 }}
              >
                <Download className="h-4 w-4" />
              </a>
            </div>

            {/* Zoom hint */}
            {hasImage && zoom === 1 && (
              <div className="absolute right-3 top-10 rounded bg-black/50 px-2 py-1 text-[10px] text-white/60 backdrop-blur">
                Click to zoom · Scroll to adjust
              </div>
            )}
          </div>

          {/* Side panel */}
          <div className="flex max-h-[92vh] flex-col overflow-y-auto p-4">
            <div className="grid grid-cols-2 gap-2 text-xs">
              <Meta label="Type" value={current.label ?? current.type} />
              <Meta label="Captured" value={new Date(current.timestamp).toLocaleString()} />
              <Meta label="Camera" value={current.camera_source ?? "—"} />
              <Meta
                label="Risk impact"
                value={current.risk_impact != null ? `+${current.risk_impact}` : "—"}
              />
            </div>

            <Section title={`Related events (±30s) · ${relatedEvents.length}`}>
              {relatedEvents.length > 0 ? (
                <EventTimeline events={relatedEvents} />
              ) : (
                <p className="text-xs text-muted-foreground">No related events in this window.</p>
              )}
            </Section>

            <Section title={`Browser activity (±30s) · ${relatedBrowser.length}`}>
              {relatedBrowser.length > 0 ? (
                <BrowserActivityTimeline items={relatedBrowser} />
              ) : (
                <p className="text-xs text-muted-foreground">No nearby browser activity.</p>
              )}
            </Section>

            <Section title="Instructor note">
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Add a note explaining your decision..."
                className="h-20 w-full rounded-xl border border-white/10 bg-white/5 p-2.5 text-xs outline-none placeholder:text-muted-foreground focus:border-primary/40"
              />
            </Section>

            <div className="mt-auto flex flex-wrap items-center gap-2 pt-3">
              <GlowButton size="sm" variant="outline" onClick={() => decide("valid")}>
                <Check className="h-4 w-4" /> Valid
              </GlowButton>
              <GlowButton size="sm" variant="ghost" onClick={() => decide("false_positive")}>
                <XCircle className="h-4 w-4" /> False positive
              </GlowButton>
              <GlowButton size="sm" variant="ghost" onClick={() => decide("needs_review")}>
                <AlertTriangle className="h-4 w-4" /> Needs review
              </GlowButton>
              <GlowButton size="sm" variant="ghost" onClick={() => decide("dismissed")}>
                <Trash2 className="h-4 w-4" /> Dismiss
              </GlowButton>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function ToolbarButton({
  children,
  onClick,
  disabled,
  ...rest
}: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="grid h-8 w-8 place-items-center rounded-full text-white/80 transition hover:bg-white/20 hover:text-white disabled:pointer-events-none disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
      {...rest}
    >
      {children}
    </button>
  );
}

function Meta({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-white/5 bg-white/[0.03] px-2.5 py-2">
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="mt-0.5 truncate text-foreground">{value}</div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mt-4">
      <h4 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
        {title}
      </h4>
      {children}
    </div>
  );
}
