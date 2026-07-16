import { ShieldCheck } from "lucide-react";
import { useReducedMotion } from "@/hooks/use-reduced-motion";

interface Props {
  size?: number;
}

export function AnimatedShield({ size = 220 }: Props) {
  const reduced = useReducedMotion();
  return (
    <div
      className="relative grid place-items-center"
      style={{ perspective: 800, width: size, height: size }}
      aria-hidden
    >
      <div
        className="absolute inset-0 rounded-full blur-2xl"
        style={{ background: "var(--gradient-glow)" }}
      />
      <div
        className={`relative grid place-items-center rounded-3xl glass-strong shadow-glow ${reduced ? "" : "animate-shield"}`}
        style={{
          width: size * 0.75,
          height: size * 0.75,
          transformStyle: "preserve-3d",
          background:
            "linear-gradient(135deg, oklch(0.3 0.06 260 / 0.6), oklch(0.18 0.03 260 / 0.6))",
        }}
      >
        <ShieldCheck className="text-primary" style={{ width: size * 0.35, height: size * 0.35 }} />
        <div className="pointer-events-none absolute inset-0 rounded-3xl glow-border" />
      </div>
    </div>
  );
}
