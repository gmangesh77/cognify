import type { LucideIcon } from "lucide-react";

interface PagePlaceholderProps {
  title: string;
  icon: LucideIcon;
}

export function PagePlaceholder({ title, icon: Icon }: PagePlaceholderProps) {
  return (
    <div className="flex flex-1 items-center justify-center">
      <div className="text-center">
        <Icon className="mx-auto h-12 w-12 text-neutral-400" />
        <h2 className="mt-4 font-heading text-xl font-semibold text-neutral-900">{title}</h2>
        <p className="mt-2 text-sm text-neutral-500">Coming Soon</p>
      </div>
    </div>
  );
}
