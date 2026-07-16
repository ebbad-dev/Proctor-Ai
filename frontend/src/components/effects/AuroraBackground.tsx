import { useReducedMotion } from "@/hooks/use-reduced-motion";

interface Props {
  className?: string;
  intensity?: "subtle" | "normal" | "strong";
}

export function AuroraBackground({ className = "", intensity = "normal" }: Props) {
  const reduced = useReducedMotion();
  const opacity = intensity === "subtle" ? 0.35 : intensity === "strong" ? 0.9 : 0.65;
  return (
    <div
      aria-hidden
      className={`pointer-events-none absolute inset-0 overflow-hidden ${className}`}
    >
      <div
        className={`absolute -inset-[20%] bg-aurora ${reduced ? "" : "animate-aurora"}`}
        style={{ opacity }}
      />
      <div className="absolute inset-0 bg-grid opacity-40" />
      <div
        className="absolute inset-0"
        style={{
          background:
            "linear-gradient(180deg, transparent 0%, oklch(0.16 0.03 260 / 0.6) 70%, oklch(0.16 0.03 260) 100%)",
        }}
      />
    </div>
  );
}
