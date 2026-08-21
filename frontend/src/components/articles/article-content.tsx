import { Fragment, useMemo, useState } from "react";
import Markdown from "react-markdown";
import rehypeRaw from "rehype-raw";
import type { Citation, ImageAsset } from "@/types/articles";
import { SectionContextToolbar } from "@/components/article/SectionContextToolbar";
import { bucketVisuals } from "@/lib/articles/bucket-visuals";
import { hasPreamble, splitBySections } from "@/lib/articles/split-sections";
import { ArticleImage, DiagramList, ReferencesList } from "./article-content-parts";

export interface SectionEditingProps {
  /** Article id for building stable section identifiers. */
  articleId: string;
  onEditText: (sectionIndex: number, sectionMarkdown: string) => void;
  onEditVisual: (sectionIndex: number) => void;
  onRefineLayout: (sectionIndex: number, sectionMarkdown: string) => void;
  /** AUTHOR-004 — redraft the section from the outline (0-based H2 index). */
  onRegenerate: (sectionIndex: number, sectionMarkdown: string) => void;
}

interface ArticleContentProps {
  bodyMarkdown: string;
  citations: Citation[];
  visuals: ImageAsset[];
  /** Optional per-section editing scaffolding (VISUAL-011 / Phase 8). */
  editing?: SectionEditingProps;
}

function stripReferencesSection(md: string): string {
  return md.split(/\n##\s+References\b/)[0].trimEnd();
}

// `sectionIdx` is the 0-based H2 (outline) index — the same space as
// section_drafts, ImagePlacement.section_index and the backend section_id
// (L-013); the preamble (if any) gets sectionIdx -1. `splitBySections` /
// `hasPreamble` live in lib/articles/split-sections.ts (shared with Visual Studio).

const PROSE_CLASS =
  "prose prose-neutral max-w-none prose-headings:font-heading prose-h2:mt-8 prose-h2:border-b prose-h2:border-neutral-200 prose-h2:pb-2 prose-h3:mt-6 prose-p:leading-7 prose-li:leading-7 prose-a:text-primary prose-a:no-underline hover:prose-a:underline";

export function ArticleContent({ bodyMarkdown, citations, visuals, editing }: ArticleContentProps) {
  const cleanMarkdown = useMemo(() => stripReferencesSection(bodyMarkdown), [bodyMarkdown]);
  const [hoveredSection, setHoveredSection] = useState<number | null>(null);
  const buckets = useMemo(() => bucketVisuals(visuals), [visuals]);
  const segments = useMemo(() => splitBySections(cleanMarkdown), [cleanMarkdown]);
  const sectionIdxOffset = hasPreamble(segments) ? 1 : 0;

  return (
    <div>
      {buckets.coverImage ? (
        <div className="mb-8">
          <ArticleImage asset={buckets.coverImage} />
        </div>
      ) : null}
      {buckets.overviewDiagrams.length > 0 ? (
        <div className="mb-8">
          <DiagramList diagrams={buckets.overviewDiagrams} />
        </div>
      ) : null}

      <div className={PROSE_CLASS}>
        {segments.map((segment, i) => {
          const sectionIdx = i - sectionIdxOffset;
          const showToolbar = editing !== undefined && sectionIdx >= 0;
          const isHovered = hoveredSection === sectionIdx;
          return (
            <Fragment key={`seg-${i}`}>
              <div
                className={
                  showToolbar
                    ? `relative -ml-3 rounded-md border-l-2 px-3 py-1 transition-colors ${
                        isHovered
                          ? "border-primary/60 bg-primary-light/30"
                          : "border-neutral-100 hover:border-neutral-300"
                      }`
                    : "relative"
                }
                data-section-index={sectionIdx}
                onMouseEnter={showToolbar ? () => setHoveredSection(sectionIdx) : undefined}
                onMouseLeave={
                  showToolbar
                    ? () => setHoveredSection((cur) => (cur === sectionIdx ? null : cur))
                    : undefined
                }
              >
                {showToolbar && editing ? (
                  <SectionContextToolbar
                    sectionId={`${editing.articleId}:${sectionIdx}`}
                    sectionIndex={sectionIdx}
                    visible={isHovered}
                    onEditText={() => editing.onEditText(sectionIdx, segment)}
                    onEditVisual={() => editing.onEditVisual(sectionIdx)}
                    onRefineLayout={() => editing.onRefineLayout(sectionIdx, segment)}
                    onRegenerate={() => editing.onRegenerate(sectionIdx, segment)}
                  />
                ) : null}
                <Markdown rehypePlugins={[rehypeRaw]}>{segment}</Markdown>
              </div>
              {sectionIdx >= 0 ? (
                <>
                  <DiagramList diagrams={buckets.sectionDiagrams.get(sectionIdx) ?? []} />
                  {(buckets.sectionImages.get(sectionIdx) ?? []).map((img) => (
                    <ArticleImage key={img.id} asset={img} />
                  ))}
                </>
              ) : null}
            </Fragment>
          );
        })}
      </div>

      <ReferencesList citations={citations} />
    </div>
  );
}
