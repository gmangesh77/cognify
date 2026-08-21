import { describe, expect, it } from "vitest";
import { locateParagraph } from "./locate-paragraph";

describe("locateParagraph", () => {
  const md = "First para.\n\nSecond para.\n\nThird.";

  it("maps a cursor inside the second paragraph", () => {
    expect(locateParagraph(md, 15)).toEqual({
      paragraphIndex: 1,
      paragraphMarkdown: "Second para.",
    });
  });

  it("clamps a cursor past the end to the last paragraph", () => {
    expect(locateParagraph(md, 999)).toEqual({
      paragraphIndex: 2,
      paragraphMarkdown: "Third.",
    });
  });
});
