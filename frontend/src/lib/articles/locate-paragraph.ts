/** Map a textarea cursor offset to the `\n\n`-separated paragraph it sits in. */
export function locateParagraph(
  markdown: string,
  cursor: number,
): { paragraphIndex: number; paragraphMarkdown: string } {
  const paragraphs = markdown.split(/\n{2,}/);
  let traversed = 0;
  for (let i = 0; i < paragraphs.length; i++) {
    const len = paragraphs[i].length + 2; // 2 for the "\n\n" separator
    if (cursor <= traversed + len) {
      return { paragraphIndex: i, paragraphMarkdown: paragraphs[i] };
    }
    traversed += len;
  }
  const last = paragraphs.length - 1;
  return {
    paragraphIndex: Math.max(0, last),
    paragraphMarkdown: paragraphs[Math.max(0, last)] ?? "",
  };
}
