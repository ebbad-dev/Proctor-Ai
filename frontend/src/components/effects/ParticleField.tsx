import { useEffect, useRef } from "react";
import { useReducedMotion } from "@/hooks/use-reduced-motion";

interface Props {
  count?: number;
  reduced?: boolean;
  className?: string;
}

// Lightweight canvas particle field. Capped, GPU-friendly draws.
export function ParticleField({ count = 50, reduced: forceReduced, className = "" }: Props) {
  const ref = useRef<HTMLCanvasElement>(null);
  const prefersReduced = useReducedMotion();
  const reduced = forceReduced ?? prefersReduced;

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const isMobile = window.innerWidth < 768;
    const n = Math.min(count, isMobile ? 20 : 60);

    let w = canvas.clientWidth;
    let h = canvas.clientHeight;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    ctx.scale(dpr, dpr);

    const particles = Array.from({ length: n }).map(() => ({
      x: Math.random() * w,
      y: Math.random() * h,
      r: Math.random() * 1.6 + 0.4,
      vx: (Math.random() - 0.5) * 0.18,
      vy: (Math.random() - 0.5) * 0.18,
      a: Math.random() * 0.5 + 0.2,
    }));

    let rafId = 0;

    const drawStatic = () => {
      ctx.clearRect(0, 0, w, h);
      ctx.fillStyle = "rgba(125, 211, 252, 0.5)";
      for (const p of particles) {
        ctx.globalAlpha = p.a;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fill();
      }
    };

    const tick = () => {
      ctx.clearRect(0, 0, w, h);
      for (const p of particles) {
        p.x += p.vx;
        p.y += p.vy;
        if (p.x < 0 || p.x > w) p.vx *= -1;
        if (p.y < 0 || p.y > h) p.vy *= -1;
        ctx.globalAlpha = p.a;
        ctx.fillStyle = "rgba(125, 211, 252, 0.6)";
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fill();
      }
      rafId = requestAnimationFrame(tick);
    };

    if (reduced) {
      drawStatic();
    } else {
      tick();
    }

    const onResize = () => {
      w = canvas.clientWidth;
      h = canvas.clientHeight;
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      ctx.scale(dpr, dpr);
    };
    window.addEventListener("resize", onResize);

    return () => {
      cancelAnimationFrame(rafId);
      window.removeEventListener("resize", onResize);
    };
  }, [count, reduced]);

  return (
    <canvas
      ref={ref}
      aria-hidden
      className={`pointer-events-none absolute inset-0 h-full w-full ${className}`}
    />
  );
}
