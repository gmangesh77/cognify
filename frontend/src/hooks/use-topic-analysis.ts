"use client";

import { useState, useCallback } from "react";
import { analyzeTopic } from "@/lib/api/trends";
import type { TopicAnalysisResult } from "@/types/api";

interface UseTopicAnalysisReturn {
  analysis: TopicAnalysisResult | null;
  isAnalyzing: boolean;
  isRegenerating: string | null;
  error: string | null;
  analyze: (title: string) => Promise<void>;
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
    } catch {
      setError("Failed to analyze topic. Please try again.");
    } finally {
      setIsAnalyzing(false);
    }
  }, []);

  const regenerateField = useCallback(
    async (title: string, field: string) => {
      if (!analysis) return;
      setIsRegenerating(field);
      try {
        const result = await analyzeTopic(title, field, analysis);
        setAnalysis(result);
      } catch {
        setError(`Failed to regenerate ${field}.`);
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
    regenerateField,
    updateField,
    reset,
  };
}
