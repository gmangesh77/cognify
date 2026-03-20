export const SOURCE_NAMES = [
  "google_trends",
  "reddit",
  "hackernews",
  "newsapi",
  "arxiv",
] as const;

export type SourceName = (typeof SOURCE_NAMES)[number];

export const SOURCE_LABELS: Record<SourceName, string> = {
  google_trends: "Google Trends",
  reddit: "Reddit",
  hackernews: "Hacker News",
  newsapi: "NewsAPI",
  arxiv: "arXiv",
};

export function getSourceLabel(source: string): string {
  return SOURCE_LABELS[source as SourceName] ?? source;
}
