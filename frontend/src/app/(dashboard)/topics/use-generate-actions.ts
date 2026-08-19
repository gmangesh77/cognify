"use client";

import { useRouter } from "next/navigation";
import { createManualTopic, createResearchSession } from "@/lib/api/trends";
import type { CreateTopicData } from "@/components/topics/create-topic-modal";
import type { ArticleParams, RankedTopic } from "@/types/api";

const TOAST_DURATION_MS = 5000;

interface UseGenerateActionsArgs {
  setToast: (message: string | null) => void;
}

interface UseGenerateActionsResult {
  handleConfirm: (topic: RankedTopic, articleParams?: ArticleParams) => Promise<void>;
  handleCreateAndGenerate: (data: CreateTopicData) => Promise<void>;
}

/**
 * Owns the "kick off research and jump to its live progress page" flow for
 * both the existing-topic (Generate modal) and manual-topic (Create + Generate)
 * paths. Extracted from the topics page so the navigation behaviour can be
 * unit-tested without mocking the page's full data-fetching surface.
 */
export function useGenerateActions({ setToast }: UseGenerateActionsArgs): UseGenerateActionsResult {
  const router = useRouter();

  function showToast(message: string) {
    setToast(message);
    setTimeout(() => setToast(null), TOAST_DURATION_MS);
  }

  async function handleConfirm(topic: RankedTopic, articleParams?: ArticleParams) {
    if (!topic.id) {
      showToast(`Cannot start research — topic has no ID. Try scanning again.`);
      return;
    }
    setToast(`Starting research for "${topic.title}"…`);
    try {
      const session = await createResearchSession(topic.id, articleParams);
      router.push(`/research/${session.session_id}`);
    } catch {
      showToast(`Failed to start research for "${topic.title}".`);
    }
  }

  async function handleCreateAndGenerate(data: CreateTopicData) {
    setToast(`Starting research for "${data.title}"…`);
    try {
      const result = await createManualTopic({
        title: data.title,
        description: data.description,
        domain: data.domain,
        keywords: data.keywords,
      });
      const topicId = result.duplicate_of || result.topic.id;
      const session = await createResearchSession(topicId, {
        target_audience: data.target_audience,
        content_tone: data.content_tone,
        preferred_angle: data.preferred_angle,
        keywords: data.keywords,
        require_outline_approval: data.require_outline_approval,
      });
      router.push(`/research/${session.session_id}`);
    } catch {
      showToast(`Failed to create topic and start research.`);
    }
  }

  return { handleConfirm, handleCreateAndGenerate };
}
