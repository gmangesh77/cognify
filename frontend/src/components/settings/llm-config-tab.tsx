import type { LlmConfig } from "@/types/settings";

interface LlmConfigTabProps {
  config: LlmConfig;
  onUpdate: (updates: Partial<LlmConfig>) => void;
}

const SELECT_CLASS =
  "mt-1 h-8 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm";

export function LlmConfigTab({ config, onUpdate }: LlmConfigTabProps) {
  return (
    <div>
      <h2 className="font-heading text-lg font-semibold text-neutral-900">
        LLM Configuration
      </h2>
      <div className="mt-4 max-w-md space-y-6">
        <div>
          <label htmlFor="primary-model" className="block text-sm font-medium text-neutral-700">
            Primary Model
          </label>
          <select
            id="primary-model"
            value={config.primaryModel}
            onChange={(e) => onUpdate({ primaryModel: e.target.value as LlmConfig["primaryModel"] })}
            className={SELECT_CLASS}
          >
            <option value="claude-opus-4">Claude Opus 4</option>
            <option value="claude-sonnet-4">Claude Sonnet 4</option>
            <option value="gpt-4o">GPT-4o</option>
          </select>
          <p className="mt-1 text-xs text-neutral-500">
            Used for final article synthesis and quality pass
          </p>
        </div>

        <div>
          <label htmlFor="drafting-model" className="block text-sm font-medium text-neutral-700">
            Drafting Model
          </label>
          <select
            id="drafting-model"
            value={config.draftingModel}
            onChange={(e) => onUpdate({ draftingModel: e.target.value as LlmConfig["draftingModel"] })}
            className={SELECT_CLASS}
          >
            <option value="claude-sonnet-4">Claude Sonnet 4</option>
            <option value="claude-opus-4">Claude Opus 4</option>
            <option value="gpt-4o-mini">GPT-4o mini</option>
          </select>
          <p className="mt-1 text-xs text-neutral-500">
            Used for section drafting and outline generation
          </p>
        </div>

        <div>
          <label htmlFor="image-model" className="block text-sm font-medium text-neutral-700">
            Image Generation
          </label>
          <select
            id="image-model"
            value={config.imageGeneration}
            onChange={(e) => onUpdate({ imageGeneration: e.target.value as LlmConfig["imageGeneration"] })}
            className={SELECT_CLASS}
          >
            <option value="stable-diffusion-xl">Stable Diffusion XL</option>
            <option value="dall-e-3">DALL-E 3</option>
            <option value="midjourney">Midjourney</option>
          </select>
          <p className="mt-1 text-xs text-neutral-500">
            Used for article hero images and illustrations
          </p>
        </div>
      </div>
    </div>
  );
}
