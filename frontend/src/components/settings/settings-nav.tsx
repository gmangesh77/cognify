import { Globe, Cpu, Key, Search, Sliders } from "lucide-react";
import { cn } from "@/lib/utils";
import type { SettingsTab } from "@/types/settings";

const TABS: { key: SettingsTab; label: string; icon: React.ElementType }[] = [
  { key: "domains", label: "Domains", icon: Globe },
  { key: "llm", label: "LLM Configuration", icon: Cpu },
  { key: "api-keys", label: "API Keys", icon: Key },
  { key: "seo", label: "SEO Defaults", icon: Search },
  { key: "general", label: "General", icon: Sliders },
];

interface SettingsNavProps {
  activeTab: SettingsTab;
  onTabChange: (tab: SettingsTab) => void;
}

export function SettingsNav({ activeTab, onTabChange }: SettingsNavProps) {
  return (
    <nav className="w-52 shrink-0 space-y-1 border-r border-neutral-200 bg-neutral-50 p-3">
      {TABS.map(({ key, label, icon: Icon }) => (
        <button
          key={key}
          onClick={() => onTabChange(key)}
          className={cn(
            "flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
            activeTab === key
              ? "bg-primary/10 text-primary"
              : "text-neutral-600 hover:bg-neutral-100"
          )}
        >
          <Icon className="h-4 w-4" />
          {label}
        </button>
      ))}
    </nav>
  );
}
