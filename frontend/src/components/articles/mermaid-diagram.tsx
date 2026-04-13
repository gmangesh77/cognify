"use client";

import { useEffect, useId, useRef, useState } from "react";

interface MermaidDiagramProps {
  syntax: string;
  caption?: string | null;
  altText?: string | null;
  fallbackUrl?: string | null;
}

let mermaidInitialized = false;

export function MermaidDiagram({
  syntax,
  caption,
  altText,
  fallbackUrl,
}: MermaidDiagramProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const reactId = useId();
  const renderId = `mermaid-${reactId.replace(/:/g, "-")}`;
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function renderDiagram() {
      try {
        const mermaid = (await import("mermaid")).default;
        if (!mermaidInitialized) {
          mermaid.initialize({
            startOnLoad: false,
            securityLevel: "strict",
            theme: "neutral",
            fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
          });
          mermaidInitialized = true;
        }
        const { svg } = await mermaid.render(renderId, syntax);
        if (!cancelled && containerRef.current) {
          containerRef.current.innerHTML = svg;
          setFailed(false);
        }
      } catch (err) {
        console.warn("mermaid render failed", err);
        if (!cancelled) {
          setFailed(true);
        }
      }
    }

    void renderDiagram();
    return () => {
      cancelled = true;
    };
  }, [syntax, renderId]);

  return (
    <figure className="my-6 rounded-lg border border-neutral-200 bg-white p-4 shadow-sm">
      {failed && fallbackUrl ? (
        <img
          src={fallbackUrl}
          alt={altText ?? "Diagram"}
          className="mx-auto max-w-full"
        />
      ) : failed ? (
        <div className="flex min-h-[120px] items-center justify-center text-sm text-neutral-500">
          Diagram could not be rendered.
        </div>
      ) : (
        <div
          ref={containerRef}
          aria-label={altText ?? "Diagram"}
          className="mermaid-diagram flex justify-center [&_svg]:h-auto [&_svg]:max-w-full"
        />
      )}
      {caption ? (
        <figcaption className="mt-3 text-center text-xs font-medium text-neutral-500">
          {caption}
        </figcaption>
      ) : null}
    </figure>
  );
}
