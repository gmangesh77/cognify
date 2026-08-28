/** Display helpers for the saved-asset gallery (INFRA-008 split). */

export function aspectStyle(aspect: string): string {
  const map: Record<string, string> = {
    "16:9": "16 / 9",
    "1:1": "1 / 1",
    "4:3": "4 / 3",
    "3:4": "3 / 4",
    "4:5": "4 / 5",
  };
  return map[aspect] ?? "16 / 9";
}

export function humanize(key: string): string {
  return key
    .split("_")
    .map((p) => p[0]!.toUpperCase() + p.slice(1))
    .join(" ");
}
