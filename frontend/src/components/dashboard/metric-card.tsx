import { cn } from "@/lib/utils";
import { TrendingUp, TrendingDown } from "lucide-react";

interface MetricCardProps {
  label: string;
  value: string;
  trend: number;
  trendDirection: "up" | "down";
  positiveDirection?: "up" | "down";
}

export function MetricCard({
  label,
  value,
  trend,
  trendDirection,
  positiveDirection = "up",
}: MetricCardProps) {
  const isPositive = trendDirection === positiveDirection;
  const TrendIcon = trendDirection === "up" ? TrendingUp : TrendingDown;
  const trendText = `${trendDirection === "up" ? "+" : "-"}${trend}%`;

  return (
    <div className="rounded-md border border-border bg-white p-6 shadow-md">
      <p className="text-sm text-neutral-500">{label}</p>
      <p className="mt-1 font-heading text-4xl font-semibold tracking-tight text-neutral-900">
        {value}
      </p>
      <div className={cn("mt-2 flex items-center gap-1 text-sm", isPositive ? "text-success" : "text-primary")}>
        <TrendIcon className="h-4 w-4" />
        <span>{trendText}</span>
      </div>
    </div>
  );
}
