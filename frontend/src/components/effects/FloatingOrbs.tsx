import { useReducedMotion } from "@/hooks/use-reduced-motion";

interface Props {
  className?: string;
}

export function FloatingOrbs({ className = "" }: Props) {
  const reduced = useReducedMotion();
  return (
    <div
      aria-hidden
      className={`pointer-events-none absolute inset-0 overflow-hidden ${className}`}
    >
      <div
        className={`absolute -top-24 -left-20 h-72 w-72 rounded-full blur-3xl ${reduced ? "" : "animate-float-y"}`}
        style={{ background: "oklch(0.78 0.16 215 / 0.35)" }}
      />
      <div
        className={`absolute top-32 right-0 h-80 w-80 rounded-full blur-3xl ${reduced ? "" : "animate-float-y"}`}
        style={{ background: "oklch(0.65 0.22 295 / 0.32)", animationDelay: "1.4s" }}
      />
      <div
        className={`absolute bottom-0 left-1/3 h-64 w-64 rounded-full blur-3xl ${reduced ? "" : "animate-float-y"}`}
        style={{ background: "oklch(0.6 0.2 250 / 0.28)", animationDelay: "2.6s" }}
      />
    </div>
  );
}
