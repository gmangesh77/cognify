"use client";

import { useState } from "react";
import { RefreshCw, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useTopicAnalysis } from "@/hooks/use-topic-analysis";
import type { ContentTone } from "@/types/api";

const TONE_OPTIONS: { value: ContentTone; label: string }[] = [
  { value: "technical-authoritative", label: "Technical & Authoritative" },
  { value: "conversational", label: "Conversational" },
  { value: "educational", label: "Educational" },
  { value: "analytical", label: "Analytical" },
  { value: "news-reporting", label: "News Reporting" },
];

interface CreateTopicModalProps {
  open: boolean;
  onClose: () => void;
  onCreateOnly: (topicData: CreateTopicData) => void;
  onCreateAndGenerate: (topicData: CreateTopicData) => void;
}

export interface CreateTopicData {
  title: string;
  description: string;
  domain: string;
  keywords: string[];
  target_audience: string;
  content_tone: ContentTone;
  preferred_angle: string;
}

export function CreateTopicModal({
  open,
  onClose,
  onCreateOnly,
  onCreateAndGenerate,
}: CreateTopicModalProps) {
  const [title, setTitle] = useState("");
  const {
    analysis,
    isAnalyzing,
    isRegenerating,
    error,
    analyze,
    regenerateField,
    updateField,
    reset,
  } = useTopicAnalysis();

  if (!open) return null;

  function handleClose() {
    setTitle("");
    reset();
    onClose();
  }

  function buildData(): CreateTopicData {
    return {
      title,
      description: analysis!.description,
      domain: analysis!.domain,
      keywords: analysis!.keywords,
      target_audience: analysis!.target_audience,
      content_tone: analysis!.content_tone as ContentTone,
      preferred_angle: analysis!.preferred_angle,
    };
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
    >
      <div
        role="dialog"
        className="w-full max-w-2xl rounded-lg bg-white p-6 shadow-lg max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="font-heading text-lg font-semibold text-neutral-900">
          Create Topic
        </h2>

        {/* Title input */}
        <div className="mt-4">
          <label className="text-sm font-medium text-neutral-700">
            Topic Title
          </label>
          <input
            type="text"
            autoFocus
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g., Zero Trust Architecture in Cloud-Native Apps"
            className="mt-1 w-full rounded-md border border-neutral-200 px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
          />
          <Button
            className="mt-2 bg-primary hover:bg-primary/90"
            size="sm"
            disabled={title.length < 3 || isAnalyzing}
            onClick={() => analyze(title)}
          >
            <Sparkles className="mr-2 h-4 w-4" />
            {isAnalyzing ? "Analyzing..." : "Analyze"}
          </Button>
        </div>

        {/* Loading skeleton */}
        {isAnalyzing && (
          <div className="mt-4 space-y-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-8 rounded-md" />
            ))}
          </div>
        )}

        {/* Error */}
        {error && (
          <p className="mt-3 text-sm text-red-600">{error}</p>
        )}

        {/* Analysis results */}
        {analysis && !isAnalyzing && (
          <div className="mt-4 space-y-4">
            <FieldWithRegenerate
              label="Description"
              field="description"
              isRegenerating={isRegenerating}
              onRegenerate={() => regenerateField(title, "description")}
            >
              <textarea
                value={analysis.description}
                onChange={(e) => updateField("description", e.target.value)}
                rows={4}
                className="w-full rounded-md border border-neutral-200 px-3 py-2 text-sm focus:border-primary focus:outline-none"
              />
            </FieldWithRegenerate>

            <FieldWithRegenerate
              label="Domain"
              field="domain"
              isRegenerating={isRegenerating}
              onRegenerate={() => regenerateField(title, "domain")}
            >
              <input
                type="text"
                value={analysis.domain}
                onChange={(e) => updateField("domain", e.target.value)}
                className="w-full rounded-md border border-neutral-200 px-3 py-2 text-sm focus:border-primary focus:outline-none"
              />
            </FieldWithRegenerate>

            <FieldWithRegenerate
              label="Keywords"
              field="keywords"
              isRegenerating={isRegenerating}
              onRegenerate={() => regenerateField(title, "keywords")}
            >
              <textarea
                value={analysis.keywords.join(", ")}
                onChange={(e) =>
                  updateField(
                    "keywords",
                    e.target.value.split(",").map((k) => k.trim()).filter(Boolean),
                  )
                }
                rows={2}
                className="w-full rounded-md border border-neutral-200 px-3 py-2 text-sm focus:border-primary focus:outline-none"
                placeholder="comma-separated keywords"
              />
            </FieldWithRegenerate>

            <FieldWithRegenerate
              label="Target Audience"
              field="target_audience"
              isRegenerating={isRegenerating}
              onRegenerate={() => regenerateField(title, "target_audience")}
            >
              <textarea
                value={analysis.target_audience}
                onChange={(e) => updateField("target_audience", e.target.value)}
                rows={2}
                className="w-full rounded-md border border-neutral-200 px-3 py-2 text-sm focus:border-primary focus:outline-none"
              />
            </FieldWithRegenerate>

            <FieldWithRegenerate
              label="Content Tone"
              field="content_tone"
              isRegenerating={isRegenerating}
              onRegenerate={() => regenerateField(title, "content_tone")}
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
              onRegenerate={() => regenerateField(title, "preferred_angle")}
            >
              <textarea
                value={analysis.preferred_angle}
                onChange={(e) => updateField("preferred_angle", e.target.value)}
                rows={3}
                className="w-full rounded-md border border-neutral-200 px-3 py-2 text-sm focus:border-primary focus:outline-none"
              />
            </FieldWithRegenerate>
          </div>
        )}

        {/* Footer */}
        <div className="mt-6 flex justify-end gap-3">
          <Button variant="ghost" onClick={handleClose}>
            Cancel
          </Button>
          {analysis && (
            <>
              <Button
                variant="outline"
                onClick={() => onCreateOnly(buildData())}
              >
                Create Topic
              </Button>
              <Button
                className="bg-primary hover:bg-primary/90"
                onClick={() => onCreateAndGenerate(buildData())}
              >
                Create & Generate Article
              </Button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function FieldWithRegenerate({
  label,
  field,
  isRegenerating,
  onRegenerate,
  children,
}: {
  label: string;
  field: string;
  isRegenerating: string | null;
  onRegenerate: () => void;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="flex items-center justify-between">
        <label className="text-sm font-medium text-neutral-700">{label}</label>
        <button
          type="button"
          onClick={onRegenerate}
          disabled={isRegenerating === field}
          className="text-neutral-400 hover:text-neutral-600 disabled:animate-spin"
          title={`Regenerate ${label.toLowerCase()}`}
        >
          <RefreshCw className="h-3.5 w-3.5" />
        </button>
      </div>
      <div className="mt-1">{children}</div>
    </div>
  );
}
