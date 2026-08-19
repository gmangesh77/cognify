"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { TrendBadge } from "@/components/common/trend-badge";
import { DomainBadge } from "@/components/common/domain-badge";
import { FieldWithRegenerate } from "@/components/topics/field-with-regenerate";
import { ReviewOutlineCheckbox } from "@/components/topics/review-outline-checkbox";
import { useTopicAnalysis } from "@/hooks/use-topic-analysis";
import type {
  RankedTopic,
  ContentTone,
  ArticleParams,
  StructuralDiagramMode,
} from "@/types/api";

const DIAGRAM_MODE_OPTIONS: { value: StructuralDiagramMode; label: string }[] = [
  { value: "illustration", label: "AI illustration (gpt-image-1)" },
  { value: "mermaid", label: "Mermaid (crisp labeled diagrams)" },
];

const TONE_OPTIONS: { value: ContentTone; label: string }[] = [
  { value: "technical-authoritative", label: "Technical & Authoritative" },
  { value: "conversational", label: "Conversational" },
  { value: "educational", label: "Educational" },
  { value: "analytical", label: "Analytical" },
  { value: "news-reporting", label: "News Reporting" },
];

interface GenerateArticleModalProps {
  topic: RankedTopic | null;
  onClose: () => void;
  onConfirm: (topic: RankedTopic, articleParams?: ArticleParams) => void;
}

export function GenerateArticleModal({
  topic,
  onClose,
  onConfirm,
}: GenerateArticleModalProps) {
  const {
    analysis,
    isAnalyzing,
    isRegenerating,
    error,
    analyzeWithSeed,
    regenerateField,
    updateField,
    reset,
  } = useTopicAnalysis();
  // Track the topic's original description (non-reactive — used only to
  // detect if the user edited it before submit). A ref avoids the
  // setState-in-effect lint rule.
  const originalDescriptionRef = useRef("");
  // UI-only choice (not part of the LLM analysis): how structural diagrams
  // are rendered. Defaults to AI illustration.
  const [diagramMode, setDiagramMode] =
    useState<StructuralDiagramMode>("illustration");
  // Opt in to reviewing the LLM-generated outline before section drafting
  // runs. Unchecked by default so the field is omitted and the server's
  // configured default applies.
  const [requireOutlineApproval, setRequireOutlineApproval] = useState(false);

  // On topic change, reset hook state and auto-analyze seeded with
  // the topic's existing description/domain/keywords so the user sees
  // their data immediately while the LLM fills in the blanks.
  useEffect(() => {
    if (!topic) {
      reset();
      return;
    }
    originalDescriptionRef.current = topic.description;
    analyzeWithSeed(topic.title, {
      description: topic.description,
      domain: topic.domain,
      keywords: topic.domain_keywords,
    });
  }, [topic, analyzeWithSeed, reset]);

  if (!topic) return null;

  function handleConfirm() {
    if (!analysis || !topic) return;
    const edited = analysis.description !== originalDescriptionRef.current;
    const params: ArticleParams = {
      target_audience: analysis.target_audience || undefined,
      content_tone: analysis.content_tone as ContentTone,
      preferred_angle: analysis.preferred_angle || undefined,
      keywords:
        analysis.keywords && analysis.keywords.length > 0
          ? analysis.keywords
          : undefined,
      topic_description_override: edited ? analysis.description : undefined,
      structural_diagram_mode: diagramMode,
      require_outline_approval: requireOutlineApproval || undefined,
    };
    onConfirm(topic, params);
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={onClose}
    >
      <div
        role="dialog"
        className="w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-xl bg-white p-6 shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="font-heading text-lg font-semibold text-neutral-900">
          Generate Article
        </h2>

        {/* Topic meta header */}
        <div className="mt-4 space-y-2">
          <div className="flex items-center gap-2">
            <TrendBadge variant={topic.trend_status} />
            <DomainBadge domain={topic.domain} />
          </div>
          <h3 className="font-heading text-base font-medium text-neutral-900">
            {topic.title}
          </h3>
          <p className="text-sm text-neutral-500">
            Score:{" "}
            <span className="font-semibold text-neutral-900">
              {topic.composite_score}
            </span>
          </p>
        </div>

        {/* Loading skeleton */}
        {isAnalyzing && (
          <div className="mt-6 space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-12 rounded-md" />
            ))}
          </div>
        )}

        {/* Error */}
        {error && <p className="mt-4 text-sm text-red-600">{error}</p>}

        {/* Editable fields */}
        {analysis && !isAnalyzing && (
          <div className="mt-6 space-y-4">
            <FieldWithRegenerate
              label="Description"
              field="description"
              isRegenerating={isRegenerating}
              onRegenerate={() => regenerateField(topic.title, "description")}
            >
              <textarea
                value={analysis.description}
                onChange={(e) => updateField("description", e.target.value)}
                rows={3}
                className="w-full rounded-md border border-neutral-200 px-3 py-2 text-sm focus:border-primary focus:outline-none"
              />
            </FieldWithRegenerate>

            <FieldWithRegenerate
              label="Keywords"
              field="keywords"
              isRegenerating={isRegenerating}
              onRegenerate={() => regenerateField(topic.title, "keywords")}
            >
              <textarea
                value={analysis.keywords.join(", ")}
                onChange={(e) =>
                  updateField(
                    "keywords",
                    e.target.value
                      .split(",")
                      .map((k) => k.trim())
                      .filter(Boolean),
                  )
                }
                rows={2}
                placeholder="comma-separated keywords"
                className="w-full rounded-md border border-neutral-200 px-3 py-2 text-sm focus:border-primary focus:outline-none"
              />
            </FieldWithRegenerate>

            <FieldWithRegenerate
              label="Target Audience"
              field="target_audience"
              isRegenerating={isRegenerating}
              onRegenerate={() =>
                regenerateField(topic.title, "target_audience")
              }
            >
              <textarea
                value={analysis.target_audience}
                onChange={(e) =>
                  updateField("target_audience", e.target.value)
                }
                rows={2}
                className="w-full rounded-md border border-neutral-200 px-3 py-2 text-sm focus:border-primary focus:outline-none"
              />
            </FieldWithRegenerate>

            <FieldWithRegenerate
              label="Content Tone"
              field="content_tone"
              isRegenerating={isRegenerating}
              onRegenerate={() => regenerateField(topic.title, "content_tone")}
            >
              <select
                value={analysis.content_tone}
                onChange={(e) => updateField("content_tone", e.target.value)}
                className="w-full rounded-md border border-neutral-200 px-3 py-2 text-sm focus:border-primary focus:outline-none"
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
              onRegenerate={() =>
                regenerateField(topic.title, "preferred_angle")
              }
            >
              <textarea
                value={analysis.preferred_angle}
                onChange={(e) =>
                  updateField("preferred_angle", e.target.value)
                }
                rows={3}
                className="w-full rounded-md border border-neutral-200 px-3 py-2 text-sm focus:border-primary focus:outline-none"
              />
            </FieldWithRegenerate>

            <div>
              <label
                htmlFor="diagram-mode"
                className="mb-1 block text-sm font-medium text-neutral-700"
              >
                Diagram style
              </label>
              <select
                id="diagram-mode"
                value={diagramMode}
                onChange={(e) =>
                  setDiagramMode(e.target.value as StructuralDiagramMode)
                }
                className="w-full rounded-md border border-neutral-200 px-3 py-2 text-sm focus:border-primary focus:outline-none"
              >
                {DIAGRAM_MODE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
              <p className="mt-1 text-xs text-neutral-500">
                Applies to structural diagrams (concept, process, comparison).
                Hero and editorial visuals always use AI illustration.
              </p>
            </div>

            <ReviewOutlineCheckbox
              checked={requireOutlineApproval}
              onChange={setRequireOutlineApproval}
            />
          </div>
        )}

        <p className="mt-4 text-sm text-neutral-500">
          This will start the content generation pipeline. Estimated time: 2-5
          minutes.
        </p>
        <div className="mt-6 flex justify-end gap-3">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={handleConfirm} disabled={!analysis || isAnalyzing}>
            Generate
          </Button>
        </div>
      </div>
    </div>
  );
}
