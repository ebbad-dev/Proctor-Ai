interface Props {
  className?: string;
}
export function GlowGrid({ className = "" }: Props) {
  return (
    <div
      aria-hidden
      className={`pointer-events-none absolute inset-0 overflow-hidden ${className}`}
    >
      <div className="absolute inset-0 bg-grid" />
      <div
        className="absolute inset-0"
        style={{
          background:
            "radial-gradient(50% 50% at 50% 0%, oklch(0.78 0.16 215 / 0.25), transparent 70%)",
        }}
      />
    </div>
  );
}
