import type { ReactNode } from "react";

import { cn } from "../../lib/utils";

interface BadgeProps {
  children: ReactNode;
  tone?: "neutral" | "good" | "warn" | "bad";
  className?: string;
}

export function Badge({ children, tone = "neutral", className }: BadgeProps) {
  const tones = {
    neutral: "bg-stone-100 text-stone-700",
    good: "bg-emerald-100 text-emerald-800",
    warn: "bg-amber-100 text-amber-800",
    bad: "bg-red-100 text-red-800"
  };
  return <span className={cn("rounded px-2 py-1 text-xs font-semibold", tones[tone], className)}>{children}</span>;
}
