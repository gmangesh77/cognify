import Markdown from "react-markdown";
import type { Citation } from "@/types/articles";

interface ArticleContentProps {
  bodyMarkdown: string;
  citations: Citation[];
}

export function ArticleContent({ bodyMarkdown, citations }: ArticleContentProps) {
  return (
    <div>
      <div className="prose prose-neutral max-w-none prose-headings:font-heading prose-h2:mt-8 prose-h2:border-b prose-h2:border-neutral-200 prose-h2:pb-2 prose-h3:mt-6 prose-p:leading-7 prose-li:leading-7">
        <Markdown>{bodyMarkdown}</Markdown>
      </div>

      <div className="mt-8 border-t border-neutral-200 pt-6">
        <h3 className="font-heading text-base font-semibold text-neutral-900">Sources</h3>
        {citations.length === 0 ? (
          <p className="mt-3 text-sm text-neutral-500">No sources</p>
        ) : (
          <ol className="mt-3 space-y-2">
            {citations.map((citation) => (
              <li key={citation.index} className="text-sm">
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
        )}
      </div>
    </div>
  );
}
