"use client";

import { useState } from "react";
import { applyTonePreset, rewriteSectionProse } from "@/lib/api/content";
import type { SectionRewriteResponse, TonePreset } from "@/types/content";

export interface AIRewriteState {
  busy: boolean;
  error: string | null;
  result: SectionRewriteResponse | null;
}

export interface UseAIRewriteArgs {
  sectionId: string;
  scope: "section" | "paragraph";
  paragraphIndex?: number;
  currentMarkdown: string;
  audiencePersona?: string | null;
}

const INITIAL_STATE: AIRewriteState = { busy: false, error: null, result: null };

/**
 * Rewrite / tone-preset calls for the AI rewrite popover (INFRA-008 split
 * from `components/article/AIRewritePopover.tsx`). Tone preset names are
 * server-side templates — the frontend never ships the prompt text.
 */
export function useAIRewrite({
  sectionId,
  scope,
  paragraphIndex,
  currentMarkdown,
  audiencePersona,
}: UseAIRewriteArgs) {
  const [state, setState] = useState<AIRewriteState>(INITIAL_STATE);

  async function runRewrite(promptText: string) {
    if (!promptText.trim()) return;
    setState((s) => ({ ...s, busy: true, error: null }));
    try {
      const res = await rewriteSectionProse({
        section_id: sectionId,
        instruction: promptText.trim(),
        scope,
        paragraph_index: paragraphIndex,
        current_markdown: currentMarkdown,
        audience_persona: audiencePersona ?? undefined,
      });
      setState({ busy: false, error: null, result: res });
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Rewrite failed";
      setState({ busy: false, error: msg, result: null });
    }
  }

  async function runPreset(preset: TonePreset) {
    if (paragraphIndex === undefined) {
      setState((s) => ({
        ...s,
        error: "Tone presets require a focused paragraph.",
      }));
      return;
    }
    setState((s) => ({ ...s, busy: true, error: null }));
    try {
      const res = await applyTonePreset({
        section_id: sectionId,
        paragraph_index: paragraphIndex,
        preset,
        current_markdown: currentMarkdown,
        audience_persona: audiencePersona ?? undefined,
      });
      setState({ busy: false, error: null, result: res });
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Preset failed";
      setState({ busy: false, error: msg, result: null });
    }
  }

  function reset() {
    setState(INITIAL_STATE);
  }

  return { state, runRewrite, runPreset, reset };
}
