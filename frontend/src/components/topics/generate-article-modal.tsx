"use client";

import { useEffect, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { TrendBadge } from "@/components/common/trend-badge";
import { DomainBadge } from "@/components/common/domain-badge";
import { ReviewOutlineCheckbox } from "@/components/topics/review-outline-checkbox";
import { ArticleParamsFields } from "@/components/topics/article-params-fields";
import { useGenerateModalState } from "@/components/topics/use-generate-modal-state";
import { BriefPicker, NEW_BRIEF } from "@/components/briefs/brief-picker";
import { BriefOptionsFields } from "@/components/briefs/brief-options-fields";
import { DiagramModeSelect } from "@/components/topics/diagram-mode-select";
import { useTopicAnalysis } from "@/hooks/use-topic-analysis";
import type { RankedTopic, ArticleParams } from "@/types/api";

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
  const gen = useGenerateModalState({ analysis, updateField });
  const { resetState } = gen;
  // Track the topic's original description (non-reactive — used only to
  // detect if the user edited it before submit). A ref avoids the
  // setState-in-effect lint rule.
  const originalDescriptionRef = useRef("");

  // On topic change, reset hook state and auto-analyze seeded with
  // the topic's existing description/domain/keywords so the user sees
  // their data immediately while the LLM fills in the blanks.
  useEffect(() => {
    if (!topic) {
      reset();
      resetState();
      return;
    }
    originalDescriptionRef.current = topic.description;
    analyzeWithSeed(topic.title, {
      description: topic.description,
      domain: topic.domain,
      keywords: topic.domain_keywords,
    });
  }, [topic, analyzeWithSeed, reset, resetState]);

  if (!topic) return null;

  function handleConfirm() {
    if (!analysis || !topic) return;
    const edited = analysis.description !== originalDescriptionRef.current;
    onConfirm(topic, gen.buildParams(analysis, edited));
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
            <BriefPicker
              briefs={gen.briefs}
              value={gen.selectedBriefId}
              onChange={gen.selectBrief}
              isLoading={gen.briefsLoading}
            />
            <ArticleParamsFields
              analysis={analysis}
              isRegenerating={isRegenerating}
              onRegenerate={(f) => regenerateField(topic.title, f)}
              onUpdate={updateField}
            />
            <BriefOptionsFields
              value={gen.options}
              onChange={gen.setOptions}
              showSave={gen.selectedBriefId === NEW_BRIEF}
            />
            <DiagramModeSelect value={gen.diagramMode} onChange={gen.setDiagramMode} />
            <ReviewOutlineCheckbox
              checked={gen.requireOutlineApproval}
              onChange={gen.setRequireOutlineApproval}
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
