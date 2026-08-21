import type { Citation, ImageAsset } from "@/types/articles";
import { MermaidDiagram } from "./mermaid-diagram";

/**
 * Renders a non-diagram visual (chart, photo, illustration) inline.
 * Uses native <img> rather than next/image so MinIO/external URLs work
 * without a Next image-loader allowlist. The asset URL has already been
 * absolutified by the backend (see _to_image_response).
 */
export function ArticleImage({ asset }: { asset: ImageAsset }) {
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

export function DiagramList({ diagrams }: { diagrams: ImageAsset[] }) {
  return (
    <>
      {diagrams.map((d) => (
        <MermaidDiagram
          key={d.id}
          syntax={d.metadata?.mermaid_syntax ?? ""}
          caption={d.caption}
          altText={d.altText}
          fallbackUrl={d.url}
        />
      ))}
    </>
  );
}

export function ReferencesList({ citations }: { citations: Citation[] }) {
  if (citations.length === 0) return null;
  return (
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
  );
}
