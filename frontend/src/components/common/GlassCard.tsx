import * as React from "react";
import { motion, type HTMLMotionProps } from "framer-motion";
import { cn } from "@/lib/utils";
import { cardHover } from "@/lib/motion";

type Props = HTMLMotionProps<"div"> & {
  glow?: boolean;
  hover?: boolean;
  strong?: boolean;
};

export const GlassCard = React.forwardRef<HTMLDivElement, Props>(
  ({ className, glow, hover, strong, children, ...props }, ref) => {
    return (
      <motion.div
        ref={ref}
        variants={hover ? cardHover : undefined}
        initial={hover ? "rest" : undefined}
        whileHover={hover ? "hover" : undefined}
        className={cn(
          "relative rounded-2xl",
          strong ? "glass-strong" : "glass",
          glow && "shadow-glow",
          className,
        )}
        {...props}
      >
        {children}
      </motion.div>
    );
  },
);
GlassCard.displayName = "GlassCard";
