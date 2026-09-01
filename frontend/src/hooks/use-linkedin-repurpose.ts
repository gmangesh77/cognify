"use client";

import { useCallback, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import type { ShowToast } from "@/components/ui/toaster";
import { publishLinkedinPost, repurposeLinkedin } from "@/lib/api/articles";
import type { LinkedInPostDraft } from "@/types/publishing";

export interface LinkedInRepurposeDeps {
  articleId: string;
  showToast: ShowToast;
}

// Shared with the modal so both sides key off the same literal.
export const NOT_CONNECTED_MESSAGE = "LinkedIn is not connected.";

type ApiErrorShape = {
  response?: { data?: { error?: { code?: string } } };
};

/** True only for the publish route's 503 platform_unavailable — a 503 from
 * the repurpose route means the LLM is unavailable, an unrelated cause,
 * and must not disable the Publish button. */
function isPlatformUnavailable(err: unknown): boolean {
  const code = (err as ApiErrorShape | null)?.response?.data?.error?.code;
  return code === "platform_unavailable";
}

function genericErrorMessage(err: unknown): string {
  return err instanceof Error ? err.message : "Request failed";
}

/** LinkedIn repurpose modal state (AUTHOR-013): generate a draft, let the
 * editor revise it, then publish the CURRENT edited text. */
export function useLinkedInRepurpose({ articleId, showToast }: LinkedInRepurposeDeps) {
  const [draft, setDraft] = useState<LinkedInPostDraft | null>(null);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [publishedUrl, setPublishedUrl] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const generate = useCallback(
    async (instruction?: string) => {
      setBusy(true);
      setError(null);
      try {
        const result = await repurposeLinkedin(articleId, instruction);
        setDraft(result);
        setText(result.text);
      } catch (err) {
        setError(genericErrorMessage(err));
      } finally {
        setBusy(false);
      }
    },
    [articleId],
  );

  const publish = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const result = await publishLinkedinPost(articleId, text);
      if (result.status === "success") {
        setPublishedUrl(result.external_url);
        showToast("Posted to LinkedIn");
        queryClient.invalidateQueries({ queryKey: ["publications"] });
      } else {
        setError(result.error_message ?? "Publish failed");
      }
    } catch (err) {
      setError(
        isPlatformUnavailable(err)
          ? NOT_CONNECTED_MESSAGE
          : genericErrorMessage(err),
      );
    } finally {
      setBusy(false);
    }
  }, [articleId, text, showToast, queryClient]);

  return { draft, text, setText, generate, publish, busy, error, publishedUrl };
}
