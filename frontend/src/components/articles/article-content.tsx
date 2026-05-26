import { Fragment, useMemo, useState } from "react";
import Markdown from "react-markdown";
import rehypeRaw from "rehype-raw";
import type { Citation, ImageAsset } from "@/types/articles";
import { SectionContextToolbar } from "@/components/article/SectionContextToolbar";
import { MermaidDiagram } from "./mermaid-diagram";

interface SectionEditingProps {
  /** Article id for building stable section identifiers. */
  articleId: string;
  onEditText: (sectionIndex: number, sectionMarkdown: string) => void;
  onEditVisual: (sectionIndex: number) => void;
  onRefineLayout: (sectionIndex: number, sectionMarkdown: string) => void;
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

function isDiagramVisual(v: ImageAsset): boolean {
  return Boolean(v.metadata?.diagram_type && v.metadata?.mermaid_syntax);
}

function splitBySections(md: string): string[] {
  return md.split(/\n(?=##\s)/);
}

// `splitBySections` uses a lookahead, so when the markdown starts directly
// with `## Heading` (the common case), segments[0] IS the first section, not
// a preamble. Backend `source_section_index` is 0-indexed into section_drafts,
// so we must align frontend `sectionIdx` to the same origin.
function hasPreamble(segments: string[]): boolean {
  return !(segments[0]?.trimStart().startsWith("##") ?? false);
}

const PROSE_CLASS =
  "prose prose-neutral max-w-none prose-headings:font-heading prose-h2:mt-8 prose-h2:border-b prose-h2:border-neutral-200 prose-h2:pb-2 prose-h3:mt-6 prose-p:leading-7 prose-li:leading-7 prose-a:text-primary prose-a:no-underline hover:prose-a:underline";

export function ArticleContent({
  bodyMarkdown,
  citations,
  visuals,
  editing,
}: ArticleContentProps) {
  const cleanMarkdown = useMemo(
    () => stripReferencesSection(bodyMarkdown),
    [bodyMarkdown],
  );
  const [hoveredSection, setHoveredSection] = useState<number | null>(null);

  const {
    overviewDiagrams,
    sectionDiagrams,
    coverImage,
    sectionImages,
    segments,
    sectionIdxOffset,
  } = useMemo(() => {
    // Section index for any visual: the planner stamps `section_index`,
    // legacy charts/diagrams use `source_section`. Read both.
    const sectionIndexOf = (v: ImageAsset): number | null => {
      const meta = v.metadata ?? {};
      const raw = meta.section_index ?? meta.source_section;
      if (raw === undefined || raw === null) return null;
      const n = typeof raw === "number" ? raw : Number.parseInt(String(raw), 10);
      return Number.isFinite(n) ? n : null;
    };

    const diagrams = visuals.filter(isDiagramVisual);
    const images = visuals.filter((v) => !isDiagramVisual(v));
    const overview = diagrams.filter((d) => sectionIndexOf(d) === -1);
    const perSection = new Map<number, ImageAsset[]>();
    for (const d of diagrams) {
      const idx = sectionIndexOf(d);
      if (idx !== null && idx >= 0) {
        const bucket = perSection.get(idx) ?? [];
        bucket.push(d);
        perSection.set(idx, bucket);
      }
    }
    // Bucket non-diagram images.
    //   * placement_anchor === "cover"  → article cover (rendered once at top)
    //   * else use section_index (new planner) OR source_section (legacy)
    //   * sections < 0 fall back to the cover slot
    // Only the FIRST cover-candidate wins — multiple heroes are not stacked.
    let cover: ImageAsset | null = null;
    const perSectionImg = new Map<number, ImageAsset[]>();
    for (const img of images) {
      const anchor = img.metadata?.placement_anchor;
      const role = img.metadata?.role_style;
      const idx = sectionIndexOf(img);
      const isCoverCandidate =
        anchor === "cover" || (anchor == null && idx == null && role === "hero");
      if (isCoverCandidate) {
        if (cover == null) cover = img; // first cover wins; ignore extra heroes
        continue;
      }
      if (idx !== null && idx >= 0) {
        const bucket = perSectionImg.get(idx) ?? [];
        bucket.push(img);
        perSectionImg.set(idx, bucket);
      } else if (cover == null) {
        // Unanchored non-hero with no section — last-resort cover.
        cover = img;
      }
    }
    const segs = splitBySections(cleanMarkdown);
    return {
      overviewDiagrams: overview,
      sectionDiagrams: perSection,
      coverImage: cover,
      sectionImages: perSectionImg,
      segments: segs,
      sectionIdxOffset: hasPreamble(segs) ? 1 : 0,
    };
  }, [cleanMarkdown, visuals]);

  return (
    <div>
      {coverImage ? (
        <div className="mb-8">
          <ArticleImage asset={coverImage} />
        </div>
      ) : null}

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
          // When the markdown has a preamble before the first `##` heading,
          // segments[0] is the preamble (sectionIdx = -1) and segments[1..]
          // map to section_drafts indices 0..N-1. When it starts directly
          // with `##` (the common case), segments[0..] map to indices 0..N-1.
          // `sectionIdxOffset` captures which case we're in.
          const sectionIdx = i - sectionIdxOffset;
          const diagramsForSection =
            sectionIdx >= 0 ? (sectionDiagrams.get(sectionIdx) ?? []) : [];
          const imagesForSection =
            sectionIdx >= 0 ? (sectionImages.get(sectionIdx) ?? []) : [];
          const showToolbar =
            editing !== undefined && sectionIdx >= 0;
          const sectionId = editing
            ? `${editing.articleId}:${sectionIdx}`
            : undefined;
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
                onMouseEnter={
                  showToolbar ? () => setHoveredSection(sectionIdx) : undefined
                }
                onMouseLeave={
                  showToolbar
                    ? () =>
                        setHoveredSection((cur) =>
                          cur === sectionIdx ? null : cur,
                        )
                    : undefined
                }
              >
                {showToolbar && sectionId ? (
                  <SectionContextToolbar
                    sectionId={sectionId}
                    sectionIndex={sectionIdx}
                    visible={hoveredSection === sectionIdx}
                    onEditText={() =>
                      editing.onEditText(sectionIdx, segment)
                    }
                    onEditVisual={() => editing.onEditVisual(sectionIdx)}
                    onRefineLayout={() =>
                      editing.onRefineLayout(sectionIdx, segment)
                    }
                  />
                ) : null}
                <Markdown rehypePlugins={[rehypeRaw]}>{segment}</Markdown>
              </div>
              {diagramsForSection.map((d) => (
                <MermaidDiagram
                  key={d.id}
                  syntax={d.metadata?.mermaid_syntax ?? ""}
                  caption={d.caption}
                  altText={d.altText}
                  fallbackUrl={d.url}
                />
              ))}
              {imagesForSection.map((img) => (
                <ArticleImage key={img.id} asset={img} />
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

/**
 * Renders a non-diagram visual (chart, photo, illustration) inline.
 * Uses native <img> rather than next/image so MinIO/external URLs work
 * without a Next image-loader allowlist. The asset URL has already been
 * absolutified by the backend (see _to_image_response).
 */
function ArticleImage({ asset }: { asset: ImageAsset }) {
  if (!asset.url) return null;
  return (
    <figure className="my-6">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={asset.url}
        alt={asset.altText ?? asset.caption ?? "Article visual"}
        className="w-full rounded-lg border border-neutral-200 shadow-sm"
        loading="lazy"
      />
      {asset.caption ? (
        <figcaption className="mt-2 text-center text-sm italic text-neutral-500">
          {asset.caption}
        </figcaption>
      ) : null}
    </figure>
  );
}
