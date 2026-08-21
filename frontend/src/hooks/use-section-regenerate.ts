import { useCallback, useRef, useState } from "react";
import { extractAnchorViolations } from "@/lib/api/anchorViolations";
import { regenerateSection } from "@/lib/api/content";
import type {
  AnchorViolationEntry,
  SectionRegenerateRequest,
  SectionRegenerateResponse,
} from "@/types/content";

export interface SectionRegenerateState {
  busy: boolean;
  error: string | null;
  violations: AnchorViolationEntry[];
  result: SectionRegenerateResponse | null;
}

const IDLE: SectionRegenerateState = {
  busy: false,
  error: null,
  violations: [],
  result: null,
};

function failureState(err: unknown): SectionRegenerateState {
  const violations = extractAnchorViolations(err);
  return {
    busy: false,
    result: null,
    violations,
    error: messageFor(err, violations),
  };
}

const STATUS_MESSAGES: Record<number, string> = {
  409: "This article has no stored outline to regenerate from.",
  429: "Too many regenerations — wait a minute and try again.",
  503: "Regenerate is not configured on the server (no LLM).",
};

function messageFor(err: unknown, violations: AnchorViolationEntry[]): string {
  if (violations.length > 0) {
    return `Regenerated text would drop ${violations.length} image anchor(s).`;
  }
  const status = (err as { response?: { status?: number } } | null)?.response?.status;
  if (status !== undefined && STATUS_MESSAGES[status]) return STATUS_MESSAGES[status];
  return err instanceof Error ? err.message : "Regenerate failed";
}

/** Local (non-cached) mutation state for one regenerate round-trip. */
export function useSectionRegenerate() {
  const [state, setState] = useState<SectionRegenerateState>(IDLE);
  // Monotonic request id: a response only lands if no newer run() started.
  const seq = useRef(0);

  const run = useCallback(async (body: SectionRegenerateRequest) => {
    const mine = ++seq.current;
    setState({ ...IDLE, busy: true });
    try {
      const result = await regenerateSection(body);
      if (mine === seq.current) setState({ ...IDLE, result });
    } catch (err) {
      if (mine !== seq.current) return;
      setState(failureState(err));
    }
  }, []);

  const reset = useCallback(() => setState(IDLE), []);

  return { ...state, run, reset };
}
