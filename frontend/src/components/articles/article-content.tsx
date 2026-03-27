import { useMemo } from "react";
import Markdown from "react-markdown";
import rehypeRaw from "rehype-raw";
import type { Citation } from "@/types/articles";

interface ArticleContentProps {
  bodyMarkdown: string;
  citations: Citation[];
}

function stripReferencesSection(md: string): string {
  return md.split(/\n##\s+References\b/)[0].trimEnd();
}

function linkifyCitations(md: string, citations: Citation[]): string {
  if (citations.length === 0) return md;
  const indices = new Set(citations.map((c) => c.index));
  return md.replace(/\[(\d+)\]/g, (match, num) => {
    const n = parseInt(num, 10);
    if (!indices.has(n)) return match;
    return `<a href="#cite-${n}" class="cite-link"><sup>${n}</sup></a>`;
  });
}

export function ArticleContent({ bodyMarkdown, citations }: ArticleContentProps) {
  const linkedMarkdown = useMemo(
    () => linkifyCitations(stripReferencesSection(bodyMarkdown), citations),
    [bodyMarkdown, citations],
  );

  return (
    <div>
      <div className="prose prose-neutral max-w-none prose-headings:font-heading prose-h2:mt-8 prose-h2:border-b prose-h2:border-neutral-200 prose-h2:pb-2 prose-h3:mt-6 prose-p:leading-7 prose-li:leading-7 prose-a:text-primary prose-a:no-underline hover:prose-a:underline">
        <Markdown rehypePlugins={[rehypeRaw]}>{linkedMarkdown}</Markdown>
      </div>

      {citations.length > 0 && (
        <div className="mt-8 border-t border-neutral-200 pt-6" id="sources">
          <h3 className="font-heading text-base font-semibold text-neutral-900">
            References ({citations.length})
          </h3>
          <ol className="mt-3 space-y-2">
            {citations.map((citation) => (
              <li key={citation.index} id={`cite-${citation.index}`} className="text-sm scroll-mt-4">
                <span className="font-medium text-neutral-400">[{citation.index}]</span>{" "}
                <a
                  href={citation.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-medium text-primary hover:underline"
                >
                  {citation.title}
                </a>
                {citation.authors.length > 0 && (
                  <span className="text-neutral-500"> — {citation.authors.join(", ")}</span>
                )}
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}
