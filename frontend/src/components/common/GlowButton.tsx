import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cn } from "@/lib/utils";

interface Props extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "ghost" | "outline";
  size?: "sm" | "md" | "lg";
  asChild?: boolean;
}

export const GlowButton = React.forwardRef<HTMLButtonElement, Props>(
  ({ className, variant = "primary", size = "md", asChild, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    const sizes = {
      sm: "h-9 px-4 text-sm",
      md: "h-11 px-6 text-sm",
      lg: "h-12 px-7 text-base",
    };
    const variants = {
      primary:
        "text-primary-foreground bg-gradient-primary shadow-glow hover:brightness-110 active:brightness-95",
      ghost: "text-foreground bg-white/5 border border-white/10 hover:bg-white/10",
      outline:
        "text-foreground border border-primary/40 hover:bg-primary/10 hover:border-primary/70",
    };
    return (
      <Comp
        ref={ref as never}
        className={cn(
          "relative inline-flex items-center justify-center gap-2 rounded-xl font-medium transition-all duration-200 disabled:opacity-50 disabled:pointer-events-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring [&_svg]:size-4",
          sizes[size],
          variants[variant],
          className,
        )}
        {...props}
      />
    );
  },
);
GlowButton.displayName = "GlowButton";
