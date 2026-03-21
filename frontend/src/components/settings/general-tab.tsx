import type { GeneralConfig } from "@/types/settings";

interface GeneralTabProps {
  config: GeneralConfig;
  onUpdate: (updates: Partial<GeneralConfig>) => void;
}

const SELECT_CLASS =
  "mt-1 h-8 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm";

export function GeneralTab({ config, onUpdate }: GeneralTabProps) {
  return (
    <div>
      <h2 className="font-heading text-lg font-semibold text-neutral-900">General</h2>
      <div className="mt-4 max-w-md space-y-6">
        <div>
          <label htmlFor="article-length" className="block text-sm font-medium text-neutral-700">
            Article Length Target
          </label>
          <select
            id="article-length"
            value={config.articleLengthTarget}
            onChange={(e) =>
              onUpdate({ articleLengthTarget: e.target.value as GeneralConfig["articleLengthTarget"] })
            }
            className={SELECT_CLASS}
          >
            <option value="1000-2000">1,000 – 2,000 words</option>
            <option value="3000-5000">3,000 – 5,000 words</option>
            <option value="5000-8000">5,000 – 8,000 words</option>
          </select>
          <p className="mt-1 text-xs text-neutral-500">
            Target word count range for generated articles
          </p>
        </div>

        <div>
          <label htmlFor="content-tone" className="block text-sm font-medium text-neutral-700">
            Content Tone
          </label>
          <select
            id="content-tone"
            value={config.contentTone}
            onChange={(e) =>
              onUpdate({ contentTone: e.target.value as GeneralConfig["contentTone"] })
            }
            className={SELECT_CLASS}
          >
            <option value="professional">Professional &amp; Analytical</option>
            <option value="casual">Casual &amp; Conversational</option>
            <option value="technical">Technical &amp; Detailed</option>
            <option value="educational">Educational &amp; Accessible</option>
          </select>
          <p className="mt-1 text-xs text-neutral-500">
            Writing style and tone for all generated content
          </p>
        </div>
      </div>
    </div>
  );
}
