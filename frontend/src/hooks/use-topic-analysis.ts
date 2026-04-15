"use client";

import { useState, useCallback } from "react";
import { AxiosError } from "axios";
import { analyzeTopic } from "@/lib/api/trends";
import type { TopicAnalysisResult } from "@/types/api";

function formatAnalyzeError(err: unknown, action: string): string {
  if (err instanceof AxiosError) {
    const status = err.response?.status;
    const detail =
      (err.response?.data as { error?: { message?: string } } | undefined)
        ?.error?.message ?? err.message;
    if (status === 429) return `Rate limit hit — wait a minute and retry.`;
    if (status === 503)
      return `LLM not configured. Set COGNIFY_ANTHROPIC_API_KEY.`;
    if (status) return `${action} failed (HTTP ${status}): ${detail}`;
    return `${action} failed: ${err.message}`;
  }
  return `${action} failed. Please try again.`;
}

interface UseTopicAnalysisReturn {
  analysis: TopicAnalysisResult | null;
  isAnalyzing: boolean;
  isRegenerating: string | null;
  error: string | null;
  analyze: (title: string) => Promise<void>;
  analyzeWithSeed: (
    title: string,
    seed: Partial<TopicAnalysisResult>,
  ) => Promise<void>;
  regenerateField: (title: string, field: string) => Promise<void>;
  updateField: <K extends keyof TopicAnalysisResult>(
    field: K,
    value: TopicAnalysisResult[K],
  ) => void;
  reset: () => void;
}

export function useTopicAnalysis(): UseTopicAnalysisReturn {
  const [analysis, setAnalysis] = useState<TopicAnalysisResult | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isRegenerating, setIsRegenerating] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const analyze = useCallback(async (title: string) => {
    setIsAnalyzing(true);
    setError(null);
    try {
      const result = await analyzeTopic(title);
      setAnalysis(result);
    } catch (err) {
      console.error("analyzeTopic failed", err);
      setError(formatAnalyzeError(err, "Topic analysis"));
    } finally {
      setIsAnalyzing(false);
    }
  }, []);

  const analyzeWithSeed = useCallback(
    async (title: string, seed: Partial<TopicAnalysisResult>) => {
      setIsAnalyzing(true);
      setError(null);
      try {
        const fresh = await analyzeTopic(title);
        // Prefer seed values where provided (e.g. topic's existing
        // description/domain), fall back to analyzer output for blanks.
        setAnalysis({
          description: seed.description || fresh.description,
          domain: seed.domain || fresh.domain,
          keywords:
            seed.keywords && seed.keywords.length > 0
              ? seed.keywords
              : fresh.keywords,
          target_audience: seed.target_audience || fresh.target_audience,
          content_tone: seed.content_tone || fresh.content_tone,
          preferred_angle: seed.preferred_angle || fresh.preferred_angle,
        });
      } catch (err) {
        console.error("analyzeTopic (seeded) failed", err);
        setError(formatAnalyzeError(err, "Topic analysis"));
      } finally {
        setIsAnalyzing(false);
      }
    },
    [],
  );

  const regenerateField = useCallback(
    async (title: string, field: string) => {
      if (!analysis) return;
      setIsRegenerating(field);
      try {
        const result = await analyzeTopic(title, field, analysis);
        setAnalysis(result);
      } catch (err) {
        console.error(`regenerate ${field} failed`, err);
        setError(formatAnalyzeError(err, `Regenerate ${field}`));
      } finally {
        setIsRegenerating(null);
      }
    },
    [analysis],
  );

  const updateField = useCallback(
    <K extends keyof TopicAnalysisResult>(
      field: K,
      value: TopicAnalysisResult[K],
    ) => {
      if (!analysis) return;
      setAnalysis({ ...analysis, [field]: value });
    },
    [analysis],
  );

  const reset = useCallback(() => {
    setAnalysis(null);
    setIsAnalyzing(false);
    setIsRegenerating(null);
    setError(null);
  }, []);

  return {
    analysis,
    isAnalyzing,
    isRegenerating,
    error,
    analyze,
    analyzeWithSeed,
    regenerateField,
    updateField,
    reset,
  };
}
