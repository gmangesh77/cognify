"use client";

import { pickGeneratedImageSrc } from "@/lib/visuals/imageSrc";
import type { ImageSpec, RenderResponse, SpecCardState } from "@/types/visuals";

/** Media area of a SpecCard, one treatment per lifecycle state (INFRA-008 split). */
export function SpecMedia({
  spec,
  state,
  render,
  generationEta,
  errorMessage,
}: {
  spec: ImageSpec;
  state: SpecCardState;
  render: RenderResponse | null;
  generationEta?: string;
  errorMessage?: string;
}) {
  const aspectStyle = aspectToStyle(spec.aspect_ratio);
  const imageSrc = render ? pickGeneratedImageSrc(render) : null;

  if (state === "idle") {
    return (
      <div
        style={aspectStyle}
        className="flex items-center justify-center rounded-md border border-dashed border-neutral-300 bg-neutral-50 text-sm text-neutral-500"
      >
        Plan to generate
      </div>
    );
  }

  if (state === "planning") {
    return (
      <div
        style={aspectStyle}
        className="flex flex-col items-center justify-center gap-2 rounded-md bg-warning-light/50 p-4 text-warning"
        role="status"
      >
        <Spinner />
        <span className="text-sm font-medium">Planning…</span>
        <ul className="mt-1 space-y-0.5 text-xs">
          <li>Reading section</li>
          <li>Matching personas</li>
          <li>Picking styles</li>
        </ul>
      </div>
    );
  }

  if (state === "generating") {
    return (
      <div
        style={aspectStyle}
        className="flex flex-col items-center justify-center gap-2 rounded-md bg-warning-light/50 p-4 text-warning"
        role="status"
      >
        <Spinner />
        <span className="text-sm font-medium">Rendering pixels…</span>
        {generationEta ? (
          <span className="text-xs text-warning/80">{generationEta}</span>
        ) : null}
      </div>
    );
  }

  if (state === "error") {
    return (
      <div
        style={aspectStyle}
        className="flex flex-col items-center justify-center gap-1 rounded-md border border-error/30 bg-error-light p-4 text-error"
        role="alert"
      >
        <span className="text-sm font-semibold">Render failed</span>
        {errorMessage ? (
          <span className="text-xs text-error/80">{errorMessage}</span>
        ) : null}
      </div>
    );
  }

  // done | refining
  if (imageSrc) {
    return (
      <div
        style={aspectStyle}
        className="relative overflow-hidden rounded-md bg-neutral-100"
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={imageSrc}
          alt={spec.alt_text || "Generated visual"}
          className="absolute inset-0 h-full w-full object-cover"
          loading="lazy"
        />
        {state === "refining" ? (
          <div
            className="absolute inset-0 flex items-end bg-info/30 p-3 text-info"
            role="status"
          >
            <span className="text-sm font-medium">
              Refining the hero · v1 → v2 in flight
            </span>
          </div>
        ) : null}
      </div>
    );
  }
  return (
    <div
      style={aspectStyle}
      className="flex items-center justify-center rounded-md border border-neutral-200 bg-neutral-50 text-sm text-neutral-500"
    >
      No render yet
    </div>
  );
}

function Spinner() {
  return (
    <span
      role="presentation"
      aria-hidden="true"
      className="inline-block h-5 w-5 animate-spin rounded-full border-2 border-warning/30 border-t-warning"
    />
  );
}

function aspectToStyle(aspect: ImageSpec["aspect_ratio"]): React.CSSProperties {
  const map: Record<ImageSpec["aspect_ratio"], string> = {
    "16:9": "16 / 9",
    "1:1": "1 / 1",
    "4:3": "4 / 3",
    "3:4": "3 / 4",
    "4:5": "4 / 5",
  };
  return { aspectRatio: map[aspect] };
}
