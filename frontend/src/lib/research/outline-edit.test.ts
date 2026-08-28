import { describe, expect, it } from "vitest";
import { averageBudget, newSection, reindex, swapSections } from "./outline-edit";
import type { OutlineSection } from "@/types/research";

function section(index: number, words: number): OutlineSection {
  return {
    index,
    title: `S${index}`,
    description: "",
    key_points: [],
    target_word_count: words,
    relevant_facets: [],
  };
}

describe("outline-edit helpers", () => {
  it("averageBudget rounds to 50 and defaults to 300", () => {
    expect(averageBudget([])).toBe(300);
    expect(averageBudget([section(0, 420), section(1, 380)])).toBe(400);
    expect(averageBudget([section(0, 10)])).toBe(50);
  });

  it("newSection inherits the average budget", () => {
    const s = newSection(2, [section(0, 200), section(1, 400)]);
    expect(s).toMatchObject({
      index: 2,
      title: "New section",
      target_word_count: 300,
    });
  });

  it("reindex renumbers sequentially", () => {
    expect(reindex([section(5, 1), section(9, 1)]).map((s) => s.index)).toEqual([0, 1]);
  });

  it("swapSections moves a section and reindexes; out-of-range is a no-op", () => {
    const input = [section(0, 1), section(1, 2), section(2, 3)];
    expect(swapSections(input, 0, 1).map((s) => s.target_word_count)).toEqual([2, 1, 3]);
    expect(swapSections(input, 0, 1).map((s) => s.index)).toEqual([0, 1, 2]);
    expect(swapSections(input, 0, -1)).toBe(input);
    expect(swapSections(input, 2, 1)).toBe(input);
  });
});
