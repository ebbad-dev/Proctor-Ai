import type { Variants, Transition } from "framer-motion";

const ease: Transition["ease"] = [0.22, 1, 0.36, 1];

export const fadeIn: Variants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { duration: 0.4, ease } },
};

export const slideUp: Variants = {
  hidden: { opacity: 0, y: 18 },
  show: { opacity: 1, y: 0, transition: { duration: 0.5, ease } },
};

export const scaleIn: Variants = {
  hidden: { opacity: 0, scale: 0.96 },
  show: { opacity: 1, scale: 1, transition: { duration: 0.45, ease } },
};

export const staggerContainer = (stagger = 0.08, delay = 0): Variants => ({
  hidden: {},
  show: { transition: { staggerChildren: stagger, delayChildren: delay } },
});

export const cardHover = {
  rest: { y: 0, scale: 1 },
  hover: { y: -4, scale: 1.01, transition: { duration: 0.25, ease } },
};

export const timelineReveal: Variants = {
  hidden: { opacity: 0, x: -12 },
  show: { opacity: 1, x: 0, transition: { duration: 0.35, ease } },
};

export const pulseGlow: Variants = {
  rest: { boxShadow: "0 0 0 0 rgba(56, 189, 248, 0)" },
  active: {
    boxShadow: ["0 0 0 0 rgba(56, 189, 248, 0.45)", "0 0 0 12px rgba(56, 189, 248, 0)"],
    transition: { duration: 2, repeat: Infinity, ease: "easeOut" },
  },
};

export const riskGaugeFill = (value: number): Variants => ({
  hidden: { pathLength: 0 },
  show: {
    pathLength: Math.max(0, Math.min(1, value / 100)),
    transition: { duration: 1.2, ease },
  },
});

export const pageTransition: Variants = {
  hidden: { opacity: 0, y: 8 },
  show: { opacity: 1, y: 0, transition: { duration: 0.35, ease } },
  exit: { opacity: 0, transition: { duration: 0.2 } },
};
