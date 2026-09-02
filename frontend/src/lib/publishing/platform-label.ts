const SPECIAL_LABELS: Record<string, string> = {
  linkedin: "LinkedIn",
  linkedin_post: "LinkedIn post",
  wordpress: "WordPress",
};

/** Display label for a publishing platform key (AUTHOR-013: `linkedin_post`
 * needs "LinkedIn post", not the generic capitalize()'s "Linkedin_post"). */
export function platformLabel(platform: string): string {
  const special = SPECIAL_LABELS[platform];
  if (special) return special;
  return platform
    .split("_")
    .map((word) => (word ? word.charAt(0).toUpperCase() + word.slice(1) : word))
    .join(" ");
}
