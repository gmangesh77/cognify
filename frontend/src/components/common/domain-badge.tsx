import { cn } from "@/lib/utils";
import { getDomainColor, getDomainLabel } from "@/types/domain";

interface DomainBadgeProps {
  domain: string;
}

export function DomainBadge({ domain }: DomainBadgeProps) {
  return (
    <span className={cn("text-[11px] font-semibold uppercase tracking-wide", getDomainColor(domain))}>
      {getDomainLabel(domain)}
    </span>
  );
}
