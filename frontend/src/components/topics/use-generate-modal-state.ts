"use client";

import { useCallback, useState } from "react";
import { NEW_BRIEF } from "@/components/briefs/brief-picker";
import type { BriefOptions } from "@/components/briefs/brief-options-fields";
import { useBriefs } from "@/hooks/use-briefs";
import type { Brief } from "@/types/brief";
import type {
  ArticleParams,
  ContentTone,
  StructuralDiagramMode,
  TopicAnalysisResult,
} from "@/types/api";

type UpdateFieldFn = (
  field: keyof TopicAnalysisResult,
  value: string | string[],
) => void;

const DEFAULT_OPTIONS: BriefOptions = {
  content_type: "article",
  length_target: "medium",
  save_as_brief: false,
  brief_name: "",
};

interface Args {
  analysis: TopicAnalysisResult | null;
  updateField: UpdateFieldFn;
}

export function useGenerateModalState({ analysis, updateField }: Args) {
  const { briefs, isLoading: briefsLoading } = useBriefs();
  const [selectedBriefId, setSelectedBriefId] = useState<string>(NEW_BRIEF);
  const [options, setOptions] = useState<BriefOptions | null>(null);
  const [diagramMode, setDiagramMode] =
    useState<StructuralDiagramMode>("illustration");
  const [requireOutlineApproval, setRequireOutlineApproval] = useState(false);

  const effectiveOptions: BriefOptions = options ?? {
    ...DEFAULT_OPTIONS,
    content_type: analysis?.suggested_brief?.content_type ?? "article",
    length_target: analysis?.suggested_brief?.length_target ?? "medium",
  };

  const applyBrief = useCallback(
    (b: Brief) => {
      if (b.target_audience) updateField("target_audience", b.target_audience);
      if (b.content_tone) updateField("content_tone", b.content_tone);
      if (b.preferred_angle) updateField("preferred_angle", b.preferred_angle);
      if (b.keywords.length) updateField("keywords", b.keywords);
      if (b.description) updateField("description", b.description);
      setDiagramMode(b.structural_diagram_mode);
      setRequireOutlineApproval(b.require_outline_approval);
      setOptions({
        ...DEFAULT_OPTIONS,
        content_type: b.content_type,
        length_target: b.length_target,
      });
    },
    [updateField],
  );

  const selectBrief = useCallback(
    (id: string) => {
      setSelectedBriefId(id);
      const brief = briefs.find((b) => b.id === id);
      if (brief) applyBrief(brief);
    },
    [briefs, applyBrief],
  );

  function buildParams(
    a: TopicAnalysisResult,
    descriptionEdited: boolean,
  ): ArticleParams {
    const isNew = selectedBriefId === NEW_BRIEF;
    return {
      target_audience: a.target_audience || undefined,
      content_tone: a.content_tone as ContentTone,
      preferred_angle: a.preferred_angle || undefined,
      keywords: a.keywords.length > 0 ? a.keywords : undefined,
      topic_description_override: descriptionEdited ? a.description : undefined,
      structural_diagram_mode: diagramMode,
      require_outline_approval: requireOutlineApproval || undefined,
      content_type: effectiveOptions.content_type,
      length_target: effectiveOptions.length_target,
      brief_id: isNew ? undefined : selectedBriefId,
      save_as_brief: isNew && effectiveOptions.save_as_brief ? true : undefined,
      brief_name:
        isNew && effectiveOptions.save_as_brief
          ? effectiveOptions.brief_name || a.suggested_brief?.name || undefined
          : undefined,
    };
  }

  const resetState = useCallback(() => {
    setSelectedBriefId(NEW_BRIEF);
    setOptions(null);
    setDiagramMode("illustration");
    setRequireOutlineApproval(false);
  }, []);

  return {
    briefs,
    briefsLoading,
    selectedBriefId,
    selectBrief,
    options: effectiveOptions,
    setOptions,
    diagramMode,
    setDiagramMode,
    requireOutlineApproval,
    setRequireOutlineApproval,
    buildParams,
    resetState,
  };
}
