import Link from "next/link";
import { FileText } from "lucide-react";

export function ArticleNotFound() {
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
