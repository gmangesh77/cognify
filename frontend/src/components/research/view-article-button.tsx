"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { fetchSessionArticle } from "@/lib/api/research";

interface ViewArticleButtonProps {
  sessionId: string;
}

export function ViewArticleButton({ sessionId }: ViewArticleButtonProps) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  async function handleClick() {
    setLoading(true);
    try {
      const result = await fetchSessionArticle(sessionId);
      if (result) router.push(`/articles/${result.article_id}`);
    } finally {
      setLoading(false);
    }
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={loading}
      className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary/90 disabled:opacity-50"
    >
      View article
    </button>
  );
}
