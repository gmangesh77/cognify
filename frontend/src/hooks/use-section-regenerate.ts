import { useCallback, useState } from "react";
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

function messageFor(err: unknown, violations: AnchorViolationEntry[]): string {
  if (violations.length > 0) {
    return `Regenerated text would drop ${violations.length} image anchor(s).`;
  }
  return err instanceof Error ? err.message : "Regenerate failed";
}

/** Local (non-cached) mutation state for one regenerate round-trip. */
export function useSectionRegenerate() {
  const [state, setState] = useState<SectionRegenerateState>(IDLE);

  const run = useCallback(async (body: SectionRegenerateRequest) => {
    setState({ ...IDLE, busy: true });
    try {
      const result = await regenerateSection(body);
      setState({ ...IDLE, result });
    } catch (err) {
      const violations = extractAnchorViolations(err);
      setState({
        busy: false,
        result: null,
        violations,
        error: messageFor(err, violations),
      });
    }
  }, []);

  const reset = useCallback(() => setState(IDLE), []);

  return { ...state, run, reset };
}
