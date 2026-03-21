import { Switch } from "@/components/ui/switch";
import type { SeoDefaults } from "@/types/settings";

const SEO_OPTIONS: { key: keyof SeoDefaults; label: string; description: string }[] = [
  {
    key: "autoMetaTags",
    label: "Auto-generate meta tags",
    description: "Generate title and description meta tags automatically",
  },
  {
    key: "keywordOptimization",
    label: "Keyword optimization",
    description: "Optimize keyword density and placement in content",
  },
  {
    key: "autoCoverImages",
    label: "Auto-generate cover images",
    description: "Create AI-generated hero images for each article",
  },
  {
    key: "includeCitations",
    label: "Include citations",
    description: "Add inline citations and references section to articles",
  },
  {
    key: "humanReviewBeforePublish",
    label: "Human review before publish",
    description: "Require manual approval before publishing articles",
  },
];

interface SeoDefaultsTabProps {
  defaults: SeoDefaults;
  onToggle: (key: keyof SeoDefaults) => void;
}

export function SeoDefaultsTab({ defaults, onToggle }: SeoDefaultsTabProps) {
  return (
    <div>
      <h2 className="font-heading text-lg font-semibold text-neutral-900">SEO Defaults</h2>
      <div className="mt-4 rounded-lg border border-neutral-200">
        {SEO_OPTIONS.map(({ key, label, description }, i) => (
          <div
            key={key}
            className={`flex items-center justify-between px-4 py-3 ${
              i < SEO_OPTIONS.length - 1 ? "border-b border-neutral-100" : ""
            }`}
          >
            <div>
              <p className="text-sm font-semibold text-neutral-900">{label}</p>
              <p className="text-xs text-neutral-500">{description}</p>
            </div>
            <Switch
              checked={defaults[key]}
              onCheckedChange={() => onToggle(key)}
            />
          </div>
        ))}
      </div>
    </div>
  );
}
