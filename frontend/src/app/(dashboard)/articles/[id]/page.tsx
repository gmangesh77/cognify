"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, FileText } from "lucide-react";
import { Header } from "@/components/layout/header";
import { ArticleContent } from "@/components/articles/article-content";
import { ArticleSidebar } from "@/components/articles/article-sidebar";
import { PublishModal } from "@/components/articles/publish-modal";
import { useArticle } from "@/hooks/use-article";
import { publishArticle } from "@/lib/api/articles";

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
  const { article } = useArticle(id);
  const [publishOpen, setPublishOpen] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  if (!article) return <NotFound />;

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
          <ArticleContent bodyMarkdown={article.bodyMarkdown} citations={article.citations} />
        </div>
        <div className="w-80 shrink-0">
          <ArticleSidebar article={article} onPublish={() => setPublishOpen(true)} />
        </div>
      </div>

      <PublishModal open={publishOpen} onClose={() => setPublishOpen(false)} onPublish={handlePublish} />

      {toast && (
        <div role="status" className="fixed bottom-6 right-6 z-50 rounded-lg bg-neutral-900 px-4 py-3 text-sm text-white shadow-lg">
          {toast}
        </div>
      )}
    </div>
  );
}
