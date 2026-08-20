"use client";

import { FieldWithRegenerate } from "@/components/topics/field-with-regenerate";
import { TONE_OPTIONS } from "@/components/topics/article-params-fields";
import type { TopicAnalysisResult } from "@/types/api";

const FIELD_CLASS =
  "w-full rounded-md border border-neutral-200 px-3 py-2 text-sm focus:border-primary focus:outline-none";

interface CreateTopicFieldsProps {
  analysis: TopicAnalysisResult;
  isRegenerating: string | null;
  onRegenerate: (field: keyof TopicAnalysisResult) => void;
  onUpdate: (field: keyof TopicAnalysisResult, value: string | string[]) => void;
}

/**
 * Editable analysis fields for the "Create Topic" modal — description,
 * domain, keywords, target audience, content tone, and preferred angle.
 * Extracted from `create-topic-modal.tsx` (Task 12 / AUTHOR-003) to keep
 * the modal under the 200-line file cap; mirrors `ArticleParamsFields`
 * but adds the Domain field, which only manual topic creation exposes.
 */
export function CreateTopicFields({
  analysis,
  isRegenerating,
  onRegenerate,
  onUpdate,
}: CreateTopicFieldsProps) {
  return (
    <>
      <FieldWithRegenerate
        label="Description"
        field="description"
        isRegenerating={isRegenerating}
        onRegenerate={() => onRegenerate("description")}
      >
        <textarea
          value={analysis.description}
          onChange={(e) => onUpdate("description", e.target.value)}
          rows={4}
          className={FIELD_CLASS}
        />
      </FieldWithRegenerate>

      <FieldWithRegenerate
        label="Domain"
        field="domain"
        isRegenerating={isRegenerating}
        onRegenerate={() => onRegenerate("domain")}
      >
        <input
          type="text"
          value={analysis.domain}
          onChange={(e) => onUpdate("domain", e.target.value)}
          className={FIELD_CLASS}
        />
      </FieldWithRegenerate>

      <FieldWithRegenerate
        label="Keywords"
        field="keywords"
        isRegenerating={isRegenerating}
        onRegenerate={() => onRegenerate("keywords")}
      >
        <textarea
          value={analysis.keywords.join(", ")}
          onChange={(e) =>
            onUpdate(
              "keywords",
              e.target.value.split(",").map((k) => k.trim()).filter(Boolean),
            )
          }
          rows={2}
          placeholder="comma-separated keywords"
          className={FIELD_CLASS}
        />
      </FieldWithRegenerate>

      <FieldWithRegenerate
        label="Target Audience"
        field="target_audience"
        isRegenerating={isRegenerating}
        onRegenerate={() => onRegenerate("target_audience")}
      >
        <textarea
          value={analysis.target_audience}
          onChange={(e) => onUpdate("target_audience", e.target.value)}
          rows={2}
          className={FIELD_CLASS}
        />
      </FieldWithRegenerate>

      <FieldWithRegenerate
        label="Content Tone"
        field="content_tone"
        isRegenerating={isRegenerating}
        onRegenerate={() => onRegenerate("content_tone")}
      >
        <select
          value={analysis.content_tone}
          onChange={(e) => onUpdate("content_tone", e.target.value)}
          className={FIELD_CLASS}
        >
          {TONE_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </FieldWithRegenerate>

      <FieldWithRegenerate
        label="Preferred Angle"
        field="preferred_angle"
        isRegenerating={isRegenerating}
        onRegenerate={() => onRegenerate("preferred_angle")}
      >
        <textarea
          value={analysis.preferred_angle}
          onChange={(e) => onUpdate("preferred_angle", e.target.value)}
          rows={3}
          className={FIELD_CLASS}
        />
      </FieldWithRegenerate>
    </>
  );
}
