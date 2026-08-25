import { cn } from "@/lib/utils";

const STATUS_STYLES = {
  live: "bg-success-light text-success",
  draft: "bg-steady-light text-steady",
  scheduled: "bg-accent-light text-accent",
  failed: "bg-primary-light text-primary",
  complete: "bg-success-light text-success", // legacy alias (dashboard union)
  published: "bg-success-light text-success",
  in_review: "bg-info-light text-info", // AUTHOR-007
  approved: "bg-success-light text-success", // AUTHOR-007
} as const;

const STATUS_LABELS = {
  live: "Live",
  draft: "Draft",
  scheduled: "Scheduled",
  failed: "Failed",
  complete: "Complete", // legacy alias (dashboard union)
  published: "Published",
  in_review: "In Review", // AUTHOR-007
  approved: "Approved", // AUTHOR-007
} as const;

interface StatusBadgeProps {
  status: keyof typeof STATUS_STYLES;
}

export function StatusBadge({ status }: StatusBadgeProps) {
  return (
    <span className={cn("inline-flex items-center rounded-pill px-2 py-0.5 text-[11px] font-medium", STATUS_STYLES[status])}>
      {STATUS_LABELS[status]}
    </span>
  );
}
