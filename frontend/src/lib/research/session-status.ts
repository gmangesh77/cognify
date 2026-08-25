/** Statuses that will never transition further — safe to render a full/final progress bar for. */
export const TERMINAL_SESSION_STATUSES = new Set([
  "article_complete",
  "article_failed",
  "failed",
  "cancelled",
  "completed",
]);

export function isTerminalSessionStatus(status: string | null | undefined): boolean {
  return status != null && TERMINAL_SESSION_STATUSES.has(status);
}

/** Backend filter values whose sessions deserve a "Resume" link on the
 * articles list (AUTHOR-007). These are FILTER values, not raw statuses:
 * "failed" is a server-side group covering failed + article_failed
 * (src/db/repositories.py status_groups). */
export const RESUMABLE_SESSION_FILTERS = [
  "generating_article",
  "awaiting_outline_review",
  "failed",
] as const;
