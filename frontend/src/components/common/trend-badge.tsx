import { cn } from "@/lib/utils";

const VARIANT_STYLES = {
  trending: "bg-primary-light text-primary",
  new: "bg-info-light text-info",
  rising: "bg-accent-light text-accent",
  steady: "bg-steady-light text-steady",
} as const;

const VARIANT_LABELS = {
  trending: "Trending",
  new: "New",
  rising: "Rising",
  steady: "Steady",
} as const;

interface TrendBadgeProps {
  variant: keyof typeof VARIANT_STYLES;
}

export function TrendBadge({ variant }: TrendBadgeProps) {
  return (
    <span className={cn("inline-flex items-center rounded-pill px-2 py-0.5 text-[11px] font-medium", VARIANT_STYLES[variant])}>
      {VARIANT_LABELS[variant]}
    </span>
  );
}
