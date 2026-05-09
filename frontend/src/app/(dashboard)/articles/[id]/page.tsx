"use client";

import { useMemo, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, FileText, History, LayoutPanelTop, Wand2 } from "lucide-react";
import { Header } from "@/components/layout/header";
import { AIRewritePopover } from "@/components/article/AIRewritePopover";
import { HumanizationDiffPanel } from "@/components/article/HumanizationDiffPanel";
import { InlineProseEditor } from "@/components/article/InlineProseEditor";
import { SectionHistoryDrawer } from "@/components/article/SectionHistoryDrawer";
import { ArticleContent } from "@/components/articles/article-content";
import { ArticleSidebar } from "@/components/articles/article-sidebar";
import { PublishModal } from "@/components/articles/publish-modal";
import { ImageImportModal } from "@/components/visuals/ImageImportModal";
import { SavedAssetGallery } from "@/components/visuals/SavedAssetGallery";
import { SectionHtmlRefinePanel } from "@/components/visuals/SectionHtmlRefinePanel";
import { VisualStudio } from "@/components/visuals/VisualStudio";
import { useArticle } from "@/hooks/use-article";
import { useDefaultPersona } from "@/hooks/use-default-persona";
import { attachVisualToArticle, publishArticle } from "@/lib/api/articles";
import type { ImageSpec, RenderResponse } from "@/types/visuals";
import { makeSectionId } from "@/lib/api/content";

interface ActiveSection {
  index: number;
  sectionId: string;
  markdown: string;
  paragraphIndex?: number;
  paragraphMarkdown?: string;
}

function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <FileText className="mb-4 h-12 w-12 text-neutral-300" />
      <h3 className="font-heading text-lg font-semibold text-neutral-700">Article not found</h3>
      <Link href="/articles" className="mt-4 text-sm font-medium text-primary hover:underline">
        &larr; Back to Articles
      </Link>
    </div>
  );
}

export default function ArticleDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { article, refetch } = useArticle(id);
  const [publishOpen, setPublishOpen] = useState(false);
  const [studioOpen, setStudioOpen] = useState(false);
  const [galleryOpen, setGalleryOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const defaultPersona = useDefaultPersona();
  const [activeSection, setActiveSection] = useState<ActiveSection | null>(null);
  const [historySectionId, setHistorySectionId] = useState<string | null>(null);
  const [popoverOpen, setPopoverOpen] = useState(false);
  const [humanizeOpen, setHumanizeOpen] = useState(false);
  const [refineLayoutOpen, setRefineLayoutOpen] = useState(false);
  const [focusVisualSection, setFocusVisualSection] = useState<number | null>(null);

  const studioSections = useMemo(() => {
    if (!article) return [];
    const segments = article.bodyMarkdown.split(/\n(?=##\s)/);
    // segments[0] is preamble; sections start at index 1, so section_index 0 = segments[1]
    return segments.slice(1).map((segment, i) => {
      const titleMatch = segment.match(/^##\s+(.+)/);
      return {
        section_index: i,
        title: titleMatch ? titleMatch[1].trim() : `Section ${i + 1}`,
        body_markdown: segment,
      };
    });
  }, [article]);

  if (!article) return <NotFound />;

  async function handleInsertVisuals(
    visuals: Array<{ spec: ImageSpec; render: RenderResponse }>,
  ) {
    let attached = 0;
    let failed = 0;
    for (const v of visuals) {
      const url = v.render.image_url;
      // We can only persist hosted URLs (MinIO/CDN). Base64 fallback
      // can't be re-served from the article endpoint without first
      // uploading to object storage — surface a clear error in that
      // case instead of writing an unusable data: URL to the DB.
      if (!url) {
        failed += 1;
        continue;
      }
      try {
        await attachVisualToArticle(id, {
          url,
          alt_text: v.spec.alt_text,
          caption: v.spec.rationale ?? null,
          metadata: {
            spec_id: v.spec.id,
            provider: v.render.provider,
            model: v.render.model,
            section_index: v.spec.placement.section_index,
            role_style: v.spec.role_style,
          },
        });
        attached += 1;
      } catch {
        failed += 1;
      }
    }
    await refetch();
    const parts: string[] = [];
    if (attached > 0) parts.push(`${attached} inserted`);
    if (failed > 0) parts.push(`${failed} failed (no hosted URL)`);
    setToast(parts.join(" · ") || "Nothing to insert");
    setTimeout(() => setToast(null), 6000);
  }

  async function handlePublish(platforms: string[]) {
    setPublishOpen(false);
    const results: string[] = [];
    for (const platform of platforms) {
      try {
        const res = await publishArticle(id, platform);
        if (res.status === "success") {
          results.push(`${platform}: published${res.external_url ? ` (${res.external_url})` : ""}`);
        } else {
          results.push(`${platform}: ${res.error_message ?? "failed"}`);
        }
      } catch {
        results.push(`${platform}: request failed`);
      }
    }
    setToast(results.join(" | "));
    setTimeout(() => setToast(null), 8000);
  }

  return (
    <div className="space-y-6">
      <Link href="/articles" className="inline-flex items-center gap-1 text-sm text-neutral-500 hover:text-neutral-700">
        <ArrowLeft className="h-4 w-4" /> Back to Articles
      </Link>

      <Header title={article.title} subtitle={article.subtitle ?? ""}>
        <div className="flex items-center gap-2">
          {article.aiGenerated && (
            <span className="rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-medium text-amber-700">
              AI Generated
            </span>
          )}
          <span className="rounded-full bg-neutral-100 px-2.5 py-0.5 text-xs font-medium text-neutral-600">
            {article.contentType}
          </span>
        </div>
      </Header>

      <div className="flex gap-8">
        <div className="min-w-0 flex-[2]">
          <div className="mb-4 flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={() => setGalleryOpen(true)}
              className="rounded-md bg-neutral-100 px-3 py-1.5 text-xs font-medium text-neutral-700 hover:bg-neutral-200"
            >
              Saved visuals
            </button>
            <button
              type="button"
              onClick={() => setImportOpen(true)}
              className="rounded-md bg-neutral-100 px-3 py-1.5 text-xs font-medium text-neutral-700 hover:bg-neutral-200"
            >
              Import image
            </button>
            <button
              type="button"
              onClick={() => setStudioOpen((v) => !v)}
              aria-pressed={studioOpen}
              className="rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-white hover:bg-primary/90"
            >
              {studioOpen ? "Hide Visual Studio" : "Open Visual Studio"}
            </button>
          </div>
          <ArticleContent
            bodyMarkdown={article.bodyMarkdown}
            citations={article.citations}
            visuals={article.visuals}
            editing={{
              articleId: id,
              onEditText: (sectionIndex, sectionMarkdown) => {
                setActiveSection({
                  index: sectionIndex,
                  sectionId: makeSectionId(id, sectionIndex),
                  markdown: sectionMarkdown,
                });
                setPopoverOpen(false);
              },
              onEditVisual: (sectionIndex) => {
                setStudioOpen(true);
                setFocusVisualSection(sectionIndex);
              },
              onRefineLayout: (sectionIndex, sectionMarkdown) => {
                // Open the section's editor + auto-open the refine panel
                // so "Refine layout" lands the user directly in the
                // SectionHtmlRefinePanel scoped to that section.
                setActiveSection({
                  index: sectionIndex,
                  sectionId: makeSectionId(id, sectionIndex),
                  markdown: sectionMarkdown,
                });
                setHumanizeOpen(false);
                setPopoverOpen(false);
                setRefineLayoutOpen(true);
              },
            }}
          />
          {activeSection ? (
            <div className="mt-4 flex flex-col gap-3">
              {/* Action row sits above the editor — buttons no longer
                  steal column width from the textarea. */}
              <div className="flex flex-wrap items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => {
                    setHumanizeOpen((v) => !v);
                    if (!humanizeOpen) setPopoverOpen(false);
                  }}
                  aria-pressed={humanizeOpen}
                  data-testid="open-humanize-panel"
                  className="inline-flex items-center gap-1 rounded-md bg-neutral-100 px-3 py-1.5 text-xs font-medium text-neutral-700 hover:bg-neutral-200"
                >
                  <Wand2 className="h-3.5 w-3.5" />
                  {humanizeOpen ? "Hide humanizer" : "Humanize"}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setPopoverOpen((v) => !v);
                    if (!popoverOpen) setHumanizeOpen(false);
                  }}
                  aria-pressed={popoverOpen}
                  className="rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-white hover:bg-primary/90"
                >
                  {popoverOpen ? "Hide AI rewrite" : "Rewrite with AI"}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setRefineLayoutOpen((v) => !v);
                    if (!refineLayoutOpen) {
                      setHumanizeOpen(false);
                      setPopoverOpen(false);
                    }
                  }}
                  aria-pressed={refineLayoutOpen}
                  className="inline-flex items-center gap-1 rounded-md bg-neutral-100 px-3 py-1.5 text-xs font-medium text-neutral-700 hover:bg-neutral-200"
                >
                  <LayoutPanelTop className="h-3.5 w-3.5" />
                  {refineLayoutOpen ? "Hide refine" : "Refine layout"}
                </button>
                <button
                  type="button"
                  onClick={() => setHistorySectionId(activeSection.sectionId)}
                  className="inline-flex items-center gap-1 rounded-md bg-neutral-100 px-3 py-1.5 text-xs font-medium text-neutral-700 hover:bg-neutral-200"
                >
                  <History className="h-3.5 w-3.5" /> History
                </button>
              </div>

              <InlineProseEditor
                key={activeSection.sectionId}
                sectionId={activeSection.sectionId}
                initialMarkdown={activeSection.markdown}
                onCancel={() => {
                  setActiveSection(null);
                  setPopoverOpen(false);
                  setHumanizeOpen(false);
                  setRefineLayoutOpen(false);
                }}
                onPersisted={(_md, vid) => {
                  setToast(`Section saved (version ${vid.slice(0, 8)})`);
                  setTimeout(() => setToast(null), 4000);
                  setActiveSection(null);
                  setPopoverOpen(false);
                  setHumanizeOpen(false);
                  setRefineLayoutOpen(false);
                }}
                onParagraphFocus={(paragraphIndex, paragraphMarkdown) =>
                  setActiveSection((prev) =>
                    prev
                      ? {
                          ...prev,
                          paragraphIndex,
                          paragraphMarkdown,
                        }
                      : prev,
                  )
                }
              />

              {humanizeOpen ? (
                <HumanizationDiffPanel
                  sectionId={activeSection.sectionId}
                  currentMarkdown={activeSection.markdown}
                  onAccept={(newMd) => {
                    setActiveSection((prev) =>
                      prev ? { ...prev, markdown: newMd } : prev,
                    );
                    setHumanizeOpen(false);
                    setToast(
                      "Humanizer suggestion staged — review then save.",
                    );
                    setTimeout(() => setToast(null), 4000);
                  }}
                  onCancel={() => setHumanizeOpen(false)}
                />
              ) : null}
              {popoverOpen ? (
                <AIRewritePopover
                  sectionId={activeSection.sectionId}
                  scope={
                    activeSection.paragraphIndex !== undefined
                      ? "paragraph"
                      : "section"
                  }
                  paragraphIndex={activeSection.paragraphIndex}
                  currentMarkdown={
                    activeSection.paragraphMarkdown ?? activeSection.markdown
                  }
                  audiencePersona={defaultPersona}
                  onAccept={(newMd, instr) => {
                    setActiveSection((prev) =>
                      prev ? { ...prev, markdown: newMd } : prev,
                    );
                    setPopoverOpen(false);
                    setToast(`Rewrite ready — review then save (${instr.slice(0, 40)})`);
                    setTimeout(() => setToast(null), 4000);
                  }}
                  onCancel={() => setPopoverOpen(false)}
                />
              ) : null}
              {refineLayoutOpen ? (
                <SectionHtmlRefinePanel
                  sectionId={activeSection.sectionId}
                  initialHtml={activeSection.markdown}
                  onApply={(newContent) => {
                    setActiveSection((prev) =>
                      prev ? { ...prev, markdown: newContent } : prev,
                    );
                    setRefineLayoutOpen(false);
                    setToast("Refine result staged — review then save.");
                    setTimeout(() => setToast(null), 4000);
                  }}
                  onCancel={() => setRefineLayoutOpen(false)}
                />
              ) : null}
            </div>
          ) : null}
        </div>
        {studioOpen ? (
          <div className="w-[560px] shrink-0">
            <VisualStudio
              article={{
                topic: {
                  title: article.title,
                  description: article.subtitle ?? article.summary,
                  domain: article.domain,
                },
                summary: article.summary,
                sections: studioSections,
              }}
              audiencePersona={defaultPersona}
              focusSectionIndex={focusVisualSection}
              onInsertIntoArticle={(visuals) => {
                void handleInsertVisuals(visuals);
              }}
              onClose={() => {
                setStudioOpen(false);
                setFocusVisualSection(null);
              }}
            />
          </div>
        ) : (
          <div className="w-80 shrink-0">
            <ArticleSidebar article={article} onPublish={() => setPublishOpen(true)} />
          </div>
        )}
      </div>

      {historySectionId ? (
        <div className="fixed bottom-6 left-6 z-50">
          <SectionHistoryDrawer
            sectionId={historySectionId}
            open
            onClose={() => setHistorySectionId(null)}
            onRestored={(newMd, vid) => {
              setActiveSection((prev) =>
                prev && prev.sectionId === historySectionId
                  ? { ...prev, markdown: newMd }
                  : prev,
              );
              setHistorySectionId(null);
              setToast(`Restored to version ${vid.slice(0, 8)}`);
              setTimeout(() => setToast(null), 4000);
            }}
          />
        </div>
      ) : null}

      <PublishModal open={publishOpen} onClose={() => setPublishOpen(false)} onPublish={handlePublish} />
      <SavedAssetGallery open={galleryOpen} onClose={() => setGalleryOpen(false)} />
      <ImageImportModal
        open={importOpen}
        onClose={() => setImportOpen(false)}
        onImported={() => setImportOpen(false)}
      />

      {toast && (
        <div role="status" className="fixed bottom-6 right-6 z-50 rounded-lg bg-neutral-900 px-4 py-3 text-sm text-white shadow-lg">
          {toast}
        </div>
      )}
    </div>
  );
}
