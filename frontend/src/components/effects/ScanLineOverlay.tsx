import { useReducedMotion } from "@/hooks/use-reduced-motion";

export function ScanLineOverlay({ className = "" }: { className?: string }) {
  const reduced = useReducedMotion();
  return (
    <div
      aria-hidden
      className={`pointer-events-none absolute inset-0 overflow-hidden rounded-[inherit] scan-lines ${className}`}
    >
      {!reduced && (
        <div
          className="absolute inset-x-0 h-24 animate-scan"
          style={{
            background:
              "linear-gradient(180deg, transparent, oklch(0.82 0.15 200 / 0.18), transparent)",
          }}
        />
      )}
    </div>
  );
}
