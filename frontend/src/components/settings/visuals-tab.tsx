import { useMemo } from "react";
import {
  IMAGE_PROVIDER_OPTIONS,
  type ImageProvider,
  type LlmConfig,
} from "@/types/settings";

interface VisualsTabProps {
  config: LlmConfig;
  onUpdate: (updates: Partial<LlmConfig>) => void;
}

const SELECT_CLASS =
  "mt-1 h-9 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm";

/**
 * Image generation settings — provider + model selectors.
 *
 * Lets admins switch between OpenAI (DALL·E 3) and Google (Gemini Flash,
 * Gemini 3 Pro, Imagen 4). Provider drives which models appear in the
 * second dropdown. Model selection is optional — when empty, the
 * provider's built-in default is used.
 *
 * Anthropic isn't an option because Claude has no image-generation API.
 */
export function VisualsTab({ config, onUpdate }: VisualsTabProps) {
  const selectedOption = useMemo(
    () =>
      IMAGE_PROVIDER_OPTIONS.find((o) => o.value === config.imageProvider) ??
      IMAGE_PROVIDER_OPTIONS[0],
    [config.imageProvider],
  );

  const requiresGoogleKey = selectedOption.vendor === "google";
  const requiresOpenAiKey = selectedOption.vendor === "openai";

  return (
    <div>
      <h2 className="font-heading text-lg font-semibold text-neutral-900">
        Image Generation
      </h2>
      <p className="mt-1 text-sm text-neutral-500">
        Choose which provider renders article hero images and section
        illustrations. Model changes apply to subsequent renders.
      </p>

      <div className="mt-6 max-w-md space-y-6">
        <div>
          <label
            htmlFor="image-provider"
            className="block text-sm font-medium text-neutral-700"
          >
            Provider
          </label>
          <select
            id="image-provider"
            value={config.imageProvider}
            onChange={(e) => {
              const next = e.target.value as ImageProvider;
              onUpdate({ imageProvider: next, imageModel: null });
            }}
            className={SELECT_CLASS}
          >
            {IMAGE_PROVIDER_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
          <p className="mt-1 text-xs text-neutral-500">
            Anthropic Claude has no image generation API, so it isn&apos;t
            listed here.
          </p>
        </div>

        <div>
          <label
            htmlFor="image-model"
            className="block text-sm font-medium text-neutral-700"
          >
            Model
          </label>
          <select
            id="image-model"
            value={config.imageModel ?? ""}
            onChange={(e) =>
              onUpdate({
                imageModel: e.target.value === "" ? null : e.target.value,
              })
            }
            className={SELECT_CLASS}
          >
            <option value="">Provider default</option>
            {selectedOption.models.map((m) => (
              <option key={m.value} value={m.value}>
                {m.label}
              </option>
            ))}
          </select>
          <p className="mt-1 text-xs text-neutral-500">
            Leave on &quot;Provider default&quot; unless you need to pin a
            specific model.
          </p>
        </div>

        <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">
          <p className="font-medium">Heads up — credentials required</p>
          {requiresOpenAiKey ? (
            <p className="mt-1">
              DALL·E 3 needs an{" "}
              <span className="font-medium">OpenAI</span> API key. Add or
              update it in the API Keys tab.
            </p>
          ) : null}
          {requiresGoogleKey ? (
            <p className="mt-1">
              Google providers need a{" "}
              <span className="font-medium">Google AI</span> API key. Add or
              update it in the API Keys tab.
            </p>
          ) : null}
        </div>
      </div>
    </div>
  );
}
