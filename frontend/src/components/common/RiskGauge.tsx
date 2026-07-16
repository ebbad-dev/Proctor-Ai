import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import type { RiskLevel } from "@/lib/types";

interface Props {
  score: number; // 0-100
  level: RiskLevel;
  size?: number;
  label?: string;
}

const colorFor: Record<RiskLevel, string> = {
  low: "oklch(0.72 0.18 155)",
  medium: "oklch(0.78 0.18 75)",
  high: "oklch(0.7 0.2 35)",
  critical: "oklch(0.6 0.26 20)",
};

export function RiskGauge({ score, level, size = 220, label = "Risk Score" }: Props) {
  const [v, setV] = useState(0);
  useEffect(() => {
    const id = requestAnimationFrame(() => setV(score));
    return () => cancelAnimationFrame(id);
  }, [score]);

  const radius = size / 2 - 14;
  const circumference = Math.PI * radius; // half circle
  const offset = circumference - (Math.max(0, Math.min(100, v)) / 100) * circumference;
  const color = colorFor[level];

  return (
    <div className="relative grid place-items-center" style={{ width: size, height: size * 0.7 }}>
      <svg width={size} height={size * 0.7} viewBox={`0 0 ${size} ${size * 0.7}`}>
        <defs>
          <linearGradient id="rg" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="oklch(0.78 0.16 215)" />
            <stop offset="100%" stopColor={color} />
          </linearGradient>
          <filter id="rgblur">
            <feGaussianBlur stdDeviation="3" />
          </filter>
        </defs>
        <path
          d={`M14,${size * 0.6} A${radius},${radius} 0 0 1 ${size - 14},${size * 0.6}`}
          fill="none"
          stroke="oklch(1 0 0 / 0.08)"
          strokeWidth="14"
          strokeLinecap="round"
        />
        <motion.path
          d={`M14,${size * 0.6} A${radius},${radius} 0 0 1 ${size - 14},${size * 0.6}`}
          fill="none"
          stroke="url(#rg)"
          strokeWidth="14"
          strokeLinecap="round"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 1.1, ease: [0.22, 1, 0.36, 1] }}
          filter="url(#rgblur)"
          opacity="0.5"
        />
        <motion.path
          d={`M14,${size * 0.6} A${radius},${radius} 0 0 1 ${size - 14},${size * 0.6}`}
          fill="none"
          stroke="url(#rg)"
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 1.1, ease: [0.22, 1, 0.36, 1] }}
        />
      </svg>
      <div className="absolute inset-x-0 bottom-2 flex flex-col items-center">
        <div className="text-[11px] uppercase tracking-widest text-muted-foreground">{label}</div>
        <div className="font-mono text-4xl font-bold tabular-nums" style={{ color }}>
          {Math.round(v)}
        </div>
        <div className="mt-0.5 text-xs uppercase tracking-wider" style={{ color }}>
          {level}
        </div>
      </div>
    </div>
  );
}
