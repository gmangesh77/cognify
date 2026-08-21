import { describe, expect, it } from "vitest";
import { studioSectionsFrom } from "./studio-sections";

describe("studioSectionsFrom", () => {
  it("indexes the first H2 as 0 when there is no prelude (L-013)", () => {
    const out = studioSectionsFrom("## Alpha\none\n\n## Beta\ntwo");
    expect(out.map((s) => [s.section_index, s.title])).toEqual([
      [0, "Alpha"],
      [1, "Beta"],
    ]);
    expect(out[0].body_markdown).toMatch(/^## Alpha/);
  });

  it("skips the prelude and still starts at 0", () => {
    const out = studioSectionsFrom("Intro para.\n\n## Alpha\none");
    expect(out).toEqual([{ section_index: 0, title: "Alpha", body_markdown: "## Alpha\none" }]);
  });
});
