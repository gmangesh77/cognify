"use client";

import { FileText } from "lucide-react";
import { Header } from "@/components/layout/header";
import { ArticleCard } from "@/components/articles/article-card";
import { useArticleList } from "@/hooks/use-article-list";

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <FileText className="mb-4 h-12 w-12 text-neutral-300" />
      <h3 className="font-heading text-lg font-semibold text-neutral-700">
        No articles generated yet
      </h3>
      <p className="mt-2 max-w-sm text-sm text-neutral-500">
        Articles will appear here after content generation completes.
      </p>
    </div>
  );
}

export default function ArticlesPage() {
  const { articles } = useArticleList();

  return (
    <div className="space-y-8">
      <Header
        title="Articles"
        subtitle="Review and publish generated articles"
      />

      {articles.length === 0 ? (
        <EmptyState />
      ) : (
        <div className="grid grid-cols-2 gap-6">
          {articles.map((article) => (
            <ArticleCard key={article.id} article={article} />
          ))}
        </div>
      )}
    </div>
  );
}
