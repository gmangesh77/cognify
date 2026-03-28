import { ExternalLink } from "lucide-react";
import type { Publication } from "@/types/publishing";

interface PublicationsTableProps {
  publications: Publication[];
  onRetry: (id: string) => void;
  retryingId: string | null;
}

function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function StatusBadge({ status }: { status: string }) {
  const config: Record<string, { label: string; className: string }> = {
    success: { label: "Live", className: "bg-green-50 text-green-600" },
    failed: { label: "Failed", className: "bg-red-50 text-red-600" },
    scheduled: { label: "Scheduled", className: "bg-yellow-50 text-yellow-600" },
  };
  const { label, className } = config[status] ?? {
    label: status,
    className: "bg-neutral-100 text-neutral-600",
  };
  return (
    <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${className}`}>
      {label}
    </span>
  );
}

function SeoScore({ score }: { score: number }) {
  const color =
    score >= 80 ? "text-green-600" : score >= 50 ? "text-yellow-600" : "text-red-600";
  return <span className={`text-sm font-medium ${color}`}>{score}</span>;
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "\u2014";
  return new Date(dateStr).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function PublicationsTable({
  publications,
  onRetry,
  retryingId,
}: PublicationsTableProps) {
  if (publications.length === 0) {
    return (
      <div className="rounded-lg border border-neutral-200 bg-white p-12 text-center">
        <p className="text-sm text-neutral-500">No publications yet</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-neutral-200 bg-white">
      <table className="w-full">
        <thead>
          <tr className="border-b border-neutral-100 bg-neutral-50">
            <th className="px-4 py-3 text-left text-xs font-medium uppercase text-neutral-500">
              Article
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium uppercase text-neutral-500">
              Platform
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium uppercase text-neutral-500">
              Status
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium uppercase text-neutral-500">
              Published
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium uppercase text-neutral-500">
              Views
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium uppercase text-neutral-500">
              SEO
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium uppercase text-neutral-500">
              Actions
            </th>
          </tr>
        </thead>
        <tbody>
          {publications.map((pub) => (
            <tr key={pub.id} className="border-b border-neutral-100 hover:bg-neutral-50">
              <td className="px-4 py-3 text-sm font-medium text-neutral-900">
                {pub.article_title}
              </td>
              <td className="px-4 py-3 text-sm text-neutral-600">
                {capitalize(pub.platform)}
              </td>
              <td className="px-4 py-3">
                <StatusBadge status={pub.status} />
              </td>
              <td className="px-4 py-3 text-sm text-neutral-600">
                {formatDate(pub.published_at)}
              </td>
              <td className="px-4 py-3 text-sm text-neutral-600">
                {pub.platform === "ghost" ? pub.view_count : "N/A"}
              </td>
              <td className="px-4 py-3">
                <SeoScore score={pub.seo_score} />
              </td>
              <td className="px-4 py-3">
                <div className="flex items-center gap-2">
                  {pub.external_url && (
                    <a
                      href={pub.external_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-neutral-400 hover:text-neutral-600"
                    >
                      <ExternalLink className="h-4 w-4" />
                    </a>
                  )}
                  {pub.status === "failed" && (
                    <button
                      type="button"
                      onClick={() => onRetry(pub.id)}
                      disabled={retryingId === pub.id}
                      className="rounded-md bg-red-50 px-2.5 py-1 text-xs font-medium text-red-600 hover:bg-red-100 disabled:opacity-50"
                    >
                      {retryingId === pub.id ? "Retrying..." : "Retry"}
                    </button>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
