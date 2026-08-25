import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { OutlineSectionEditor } from "./outline-section-editor";
import type { OutlineSection } from "@/types/research";

const baseSection: OutlineSection = {
  index: 0,
  title: "Introduction",
  description: "Set the stage",
  key_points: ["point a", "point b"],
  target_word_count: 200,
  relevant_facets: [0],
};

function renderEditor(section: OutlineSection = baseSection) {
  const onChange = vi.fn();
  render(
    <OutlineSectionEditor
      section={section}
      index={0}
      total={1}
      onChange={onChange}
      onMoveUp={vi.fn()}
      onMoveDown={vi.fn()}
      onDelete={vi.fn()}
    />,
  );
  return onChange;
}

describe("OutlineSectionEditor word budget", () => {
  it("shows the section word budget chip", () => {
    renderEditor({ ...baseSection, target_word_count: 450 });
    expect(screen.getByText("~450 words")).toBeInTheDocument();
  });
});

describe("OutlineSectionEditor key points", () => {
  it("filters out blank lines when the key points textarea changes", () => {
    const onChange = renderEditor();
    const textarea = screen.getByLabelText("Section 1 key points");
    fireEvent.change(textarea, {
      target: { value: "point a\n\npoint b\n   \npoint c" },
    });
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ key_points: ["point a", "point b", "point c"] }),
    );
  });

  it("trims surrounding whitespace on each retained line", () => {
    const onChange = renderEditor();
    const textarea = screen.getByLabelText("Section 1 key points");
    fireEvent.change(textarea, { target: { value: "  point a  \n  point b  " } });
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ key_points: ["point a", "point b"] }),
    );
  });

  it("produces an empty array when every line is blank", () => {
    const onChange = renderEditor();
    const textarea = screen.getByLabelText("Section 1 key points");
    fireEvent.change(textarea, { target: { value: "\n \n" } });
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ key_points: [] }),
    );
  });
});
