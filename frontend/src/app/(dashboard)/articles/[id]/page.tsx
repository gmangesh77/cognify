"use client";

import { useCallback, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { Header } from "@/components/layout/header";
import {
  SectionEditingWorkbench,
  type ActiveSection,
  type WorkbenchPanel,
} from "@/components/article/SectionEditingWorkbench";
import { SectionHistoryDrawer } from "@/components/article/SectionHistoryDrawer";
import { ArticleContent } from "@/components/articles/article-content";
import { ArticleDetailToolbar } from "@/components/articles/article-detail-toolbar";
import { ArticleNotFound } from "@/components/articles/article-not-found";
import { ArticleSidebar } from "@/components/articles/article-sidebar";
import { PublishModal } from "@/components/articles/publish-modal";
import { ImageImportModal } from "@/components/visuals/ImageImportModal";
import { SavedAssetGallery } from "@/components/visuals/SavedAssetGallery";
import { VisualStudio } from "@/components/visuals/VisualStudio";
import { useArticle } from "@/hooks/use-article";
import { useArticleActions } from "@/hooks/use-article-actions";
import { useDefaultPersona } from "@/hooks/use-default-persona";
import { makeSectionId } from "@/lib/api/content";
import { studioSectionsFrom } from "@/lib/articles/studio-sections";

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
  const [initialPanel, setInitialPanel] = useState<WorkbenchPanel | null>(null);
  const [historySectionId, setHistorySectionId] = useState<string | null>(null);
  const [focusVisualSection, setFocusVisualSection] = useState<number | null>(null);

  const showToast = useCallback((message: string, ms = 4000) => {
    setToast(message);
    setTimeout(() => setToast(null), ms);
  }, []);
  const { insertVisuals, publish } = useArticleActions({ id, refetch, showToast });
  // Outline-space sections (L-013) — shared splitter with ArticleContent.
  const studioSections = useMemo(
    () => (article ? studioSectionsFrom(article.bodyMarkdown) : []),
    [article],
  );

  if (!article) return <ArticleNotFound />;

  const openSection = (sectionIndex: number, markdown: string, panel: WorkbenchPanel | null) => {
    setActiveSection({ index: sectionIndex, sectionId: makeSectionId(id, sectionIndex), markdown });
    setInitialPanel(panel);
  };

  return (
    <div className="space-y-6">
      <Link
        href="/articles"
        className="inline-flex items-center gap-1 text-sm text-neutral-500 hover:text-neutral-700"
      >
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
          <ArticleDetailToolbar
            studioOpen={studioOpen}
            onOpenGallery={() => setGalleryOpen(true)}
            onOpenImport={() => setImportOpen(true)}
            onToggleStudio={() => setStudioOpen((v) => !v)}
          />
          <ArticleContent
            bodyMarkdown={article.bodyMarkdown}
            citations={article.citations}
            visuals={article.visuals}
            editing={{
              articleId: id,
              onEditText: (i, md) => openSection(i, md, null),
              onEditVisual: (i) => {
                setStudioOpen(true);
                setFocusVisualSection(i);
              },
              onRefineLayout: (i, md) => openSection(i, md, "refine"),
              onRegenerate: (i, md) => openSection(i, md, "regenerate"),
            }}
          />
          {activeSection ? (
            <SectionEditingWorkbench
              key={`${activeSection.sectionId}-${initialPanel ?? "none"}`}
              articleId={id}
              section={activeSection}
              defaultPersona={defaultPersona}
              initialPanel={initialPanel}
              onChange={setActiveSection}
              onToast={showToast}
              onOpenHistory={setHistorySectionId}
              onPersisted={() => {
                void refetch();
              }}
            />
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
                void insertVisuals(visuals);
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
                prev && prev.sectionId === historySectionId ? { ...prev, markdown: newMd } : prev,
              );
              setHistorySectionId(null);
              showToast(`Restored to version ${vid.slice(0, 8)}`);
            }}
          />
        </div>
      ) : null}

      <PublishModal
        open={publishOpen}
        onClose={() => setPublishOpen(false)}
        onPublish={(platforms) => {
          setPublishOpen(false);
          void publish(platforms);
        }}
      />
      <SavedAssetGallery open={galleryOpen} onClose={() => setGalleryOpen(false)} />
      <ImageImportModal
        open={importOpen}
        onClose={() => setImportOpen(false)}
        onImported={() => setImportOpen(false)}
      />

      {toast && (
        <div
          role="status"
          className="fixed bottom-6 right-6 z-50 rounded-lg bg-neutral-900 px-4 py-3 text-sm text-white shadow-lg"
        >
          {toast}
        </div>
      )}
    </div>
  );
}
