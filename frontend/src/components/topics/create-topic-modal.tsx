"use client";

import { useState } from "react";
import { Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ReviewOutlineCheckbox } from "@/components/topics/review-outline-checkbox";
import { DiagramModeSelect } from "@/components/topics/diagram-mode-select";
import { CreateTopicFields } from "@/components/topics/create-topic-fields";
import { BriefOptionsFields, type BriefOptions } from "@/components/briefs/brief-options-fields";
import { useTopicAnalysis } from "@/hooks/use-topic-analysis";
import type { ContentTone, StructuralDiagramMode } from "@/types/api";
import type { BriefContentType, LengthTarget } from "@/types/brief";

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
  structural_diagram_mode: StructuralDiagramMode;
  content_type: BriefContentType;
  length_target: LengthTarget;
  require_outline_approval?: boolean;
}

export function CreateTopicModal({
  open,
  onClose,
  onCreateOnly,
  onCreateAndGenerate,
}: CreateTopicModalProps) {
  const [title, setTitle] = useState("");
  // Opt in to reviewing the LLM-generated outline before section drafting
  // runs (only meaningful for the "Create & Generate Article" path).
  const [requireOutlineApproval, setRequireOutlineApproval] = useState(false);
  const [diagramMode, setDiagramMode] =
    useState<StructuralDiagramMode>("illustration");
  const [options, setOptions] = useState<BriefOptions>({
    content_type: "article",
    length_target: "medium",
    save_as_brief: false,
    brief_name: "",
  });
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
    setRequireOutlineApproval(false);
    setDiagramMode("illustration");
    setOptions({
      content_type: "article",
      length_target: "medium",
      save_as_brief: false,
      brief_name: "",
    });
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
      structural_diagram_mode: diagramMode,
      content_type: options.content_type,
      length_target: options.length_target,
      require_outline_approval: requireOutlineApproval || undefined,
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
            <CreateTopicFields
              analysis={analysis}
              isRegenerating={isRegenerating}
              onRegenerate={(f) => regenerateField(title, f)}
              onUpdate={updateField}
            />

            <BriefOptionsFields
              value={options}
              onChange={setOptions}
              showSave={false}
            />
            <DiagramModeSelect value={diagramMode} onChange={setDiagramMode} />

            <ReviewOutlineCheckbox
              checked={requireOutlineApproval}
              onChange={setRequireOutlineApproval}
            />
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

