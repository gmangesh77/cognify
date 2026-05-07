import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { WordDiffEntry } from "@/types/content";
import { WordDiffView } from "./WordDiffView";

describe("WordDiffView", () => {
  it("renders insert ops with the success treatment", () => {
    const ops: WordDiffEntry[] = [
      { kind: "equal", before: "the ", after: "the " },
      { kind: "insert", before: "", after: "very " },
      { kind: "equal", before: "quick fox", after: "quick fox" },
    ];
    render(<WordDiffView ops={ops} />);
    const insert = screen.getByTestId("diff-insert");
    expect(insert).toHaveTextContent("very");
  });

  it("renders delete ops with the strikethrough treatment", () => {
    const ops: WordDiffEntry[] = [
      { kind: "delete", before: "obsolete ", after: "" },
      { kind: "equal", before: "body", after: "body" },
    ];
    render(<WordDiffView ops={ops} />);
    const del = screen.getByTestId("diff-delete");
    expect(del).toHaveTextContent("obsolete");
  });

  it("renders replace ops as before-then-after", () => {
    const ops: WordDiffEntry[] = [
      { kind: "replace", before: "quick", after: "brown" },
    ];
    render(<WordDiffView ops={ops} />);
    const replace = screen.getByTestId("diff-replace");
    expect(replace).toHaveTextContent("quick");
    expect(replace).toHaveTextContent("brown");
  });
});
