import { describe, expect, it } from "vitest";
import type { ImageAsset } from "@/types/articles";
import { bucketVisuals } from "./bucket-visuals";

function asset(id: string, metadata: ImageAsset["metadata"]): ImageAsset {
  return { id, url: `https://x/${id}.png`, caption: null, altText: null, metadata };
}

describe("bucketVisuals", () => {
  it("first cover candidate wins; extra heroes are ignored", () => {
    const out = bucketVisuals([
      asset("h1", { placement_anchor: "cover", role_style: "hero" }),
      asset("h2", { role_style: "hero" }),
    ]);
    expect(out.coverImage?.id).toBe("h1");
    expect(out.sectionImages.size).toBe(0);
  });

  it("buckets images by section_index (planner) or source_section (legacy)", () => {
    const out = bucketVisuals([
      asset("a", { section_index: 1, role_style: "concept" }),
      asset("b", { source_section: 1 }),
      asset("c", { section_index: 0 }),
    ]);
    expect(out.sectionImages.get(1)?.map((v) => v.id)).toEqual(["a", "b"]);
    expect(out.sectionImages.get(0)?.map((v) => v.id)).toEqual(["c"]);
  });

  it("splits mermaid diagrams into overview (-1) and per-section buckets", () => {
    const out = bucketVisuals([
      asset("d0", { diagram_type: "flowchart", mermaid_syntax: "graph TD", section_index: -1 }),
      asset("d1", { diagram_type: "flowchart", mermaid_syntax: "graph TD", source_section: 2 }),
    ]);
    expect(out.overviewDiagrams.map((d) => d.id)).toEqual(["d0"]);
    expect(out.sectionDiagrams.get(2)?.map((d) => d.id)).toEqual(["d1"]);
  });
});
