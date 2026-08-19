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
