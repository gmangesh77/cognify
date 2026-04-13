import { Fragment, useMemo } from "react";
import Markdown from "react-markdown";
import rehypeRaw from "rehype-raw";
import type { Citation, ImageAsset } from "@/types/articles";
import { MermaidDiagram } from "./mermaid-diagram";

interface ArticleContentProps {
  bodyMarkdown: string;
  citations: Citation[];
  visuals: ImageAsset[];
}

function stripReferencesSection(md: string): string {
  return md.split(/\n##\s+References\b/)[0].trimEnd();
}

function isDiagramVisual(v: ImageAsset): boolean {
  return Boolean(v.metadata?.diagram_type && v.metadata?.mermaid_syntax);
}

function splitBySections(md: string): string[] {
  return md.split(/\n(?=##\s)/);
}

const PROSE_CLASS =
  "prose prose-neutral max-w-none prose-headings:font-heading prose-h2:mt-8 prose-h2:border-b prose-h2:border-neutral-200 prose-h2:pb-2 prose-h3:mt-6 prose-p:leading-7 prose-li:leading-7 prose-a:text-primary prose-a:no-underline hover:prose-a:underline";

export function ArticleContent({
  bodyMarkdown,
  citations,
  visuals,
}: ArticleContentProps) {
  const cleanMarkdown = useMemo(
    () => stripReferencesSection(bodyMarkdown),
    [bodyMarkdown],
  );

  const { overviewDiagrams, sectionDiagrams, segments } = useMemo(() => {
    const diagrams = visuals.filter(isDiagramVisual);
    const overview = diagrams.filter((d) => d.metadata?.source_section === -1);
    const perSection = new Map<number, ImageAsset[]>();
    for (const d of diagrams) {
      const idx = d.metadata?.source_section ?? -1;
      if (idx >= 0) {
        const bucket = perSection.get(idx) ?? [];
        bucket.push(d);
        perSection.set(idx, bucket);
      }
    }
    return {
      overviewDiagrams: overview,
      sectionDiagrams: perSection,
      segments: splitBySections(cleanMarkdown),
    };
  }, [cleanMarkdown, visuals]);

  return (
    <div>
      {overviewDiagrams.length > 0 ? (
        <div className="mb-8">
          {overviewDiagrams.map((d) => (
            <MermaidDiagram
              key={d.id}
              syntax={d.metadata?.mermaid_syntax ?? ""}
              caption={d.caption}
              altText={d.altText}
              fallbackUrl={d.url}
            />
          ))}
        </div>
      ) : null}

      <div className={PROSE_CLASS}>
        {segments.map((segment, i) => {
          // segments[0] = preamble (before any ##); segments[1..] each start
          // with an `##` heading. Section index within section_drafts is i-1
          // for i >= 1. Overview diagrams render above this block.
          const sectionIdx = i - 1;
          const diagramsForSection =
            sectionIdx >= 0 ? (sectionDiagrams.get(sectionIdx) ?? []) : [];
          return (
            <Fragment key={`seg-${i}`}>
              <Markdown rehypePlugins={[rehypeRaw]}>{segment}</Markdown>
              {diagramsForSection.map((d) => (
                <MermaidDiagram
                  key={d.id}
                  syntax={d.metadata?.mermaid_syntax ?? ""}
                  caption={d.caption}
                  altText={d.altText}
                  fallbackUrl={d.url}
                />
              ))}
            </Fragment>
          );
        })}
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
