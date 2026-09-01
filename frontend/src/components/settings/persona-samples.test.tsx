import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { countWords, PersonaSamples } from "./persona-samples";
import type { PersonaDetail } from "@/types/persona";

const persona: PersonaDetail = {
  id: "p1",
  name: "House Style",
  description: null,
  sample_count: 1,
  ready: false,
  updated_at: "2026-09-01T00:00:00Z",
  fingerprint: null,
  samples: [{ id: "s1", word_count: 200, preview: "Some prose that goes on…", created_at: "2026-09-01T00:00:00Z" }],
};

describe("countWords", () => {
  it("counts only letter runs, mirroring the backend regex", () => {
    expect(countWords("Hello, world! It's a test-run.")).toBe(6);
    expect(countWords("")).toBe(0);
    expect(countWords("   ")).toBe(0);
  });
});

const shortText = "one two three";
const longText = Array.from({ length: 150 }, (_, i) => `word${i}`).join(" ");

describe("PersonaSamples", () => {
  it("shows a live word count that updates as you type", () => {
    render(<PersonaSamples persona={persona} canEdit violations={[]} onAdd={vi.fn()} onRemove={vi.fn()} />);
    expect(screen.getByText("0 / 150 words")).toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText(/Paste a writing sample/), { target: { value: shortText } });
    expect(screen.getByText("3 / 150 words")).toBeInTheDocument();
  });

  it("disables Add sample under 150 words and enables it at/above the minimum", () => {
    render(<PersonaSamples persona={persona} canEdit violations={[]} onAdd={vi.fn()} onRemove={vi.fn()} />);
    const addButton = screen.getByRole("button", { name: "Add sample" });
    fireEvent.change(screen.getByPlaceholderText(/Paste a writing sample/), { target: { value: shortText } });
    expect(addButton).toBeDisabled();
    fireEvent.change(screen.getByPlaceholderText(/Paste a writing sample/), { target: { value: longText } });
    expect(addButton).not.toBeDisabled();
  });

  it("disables Add sample while mutating even with enough words", () => {
    render(<PersonaSamples persona={persona} canEdit violations={[]} onAdd={vi.fn()} onRemove={vi.fn()} isMutating />);
    fireEvent.change(screen.getByPlaceholderText(/Paste a writing sample/), { target: { value: longText } });
    expect(screen.getByRole("button", { name: "Add sample" })).toBeDisabled();
  });

  it("calls onAdd with the full text and clears the textarea", () => {
    const onAdd = vi.fn();
    render(<PersonaSamples persona={persona} canEdit violations={[]} onAdd={onAdd} onRemove={vi.fn()} />);
    const textarea = screen.getByPlaceholderText(/Paste a writing sample/);
    fireEvent.change(textarea, { target: { value: longText } });
    fireEvent.click(screen.getByRole("button", { name: "Add sample" }));
    expect(onAdd).toHaveBeenCalledWith(longText);
    expect(textarea).toHaveValue("");
  });

  it("renders violations", () => {
    render(<PersonaSamples persona={persona} canEdit violations={["need 5 samples of 150+ words, have 1"]} onAdd={vi.fn()} onRemove={vi.fn()} />);
    expect(screen.getByText("need 5 samples of 150+ words, have 1")).toBeInTheDocument();
  });

  it("lists existing samples and calls onRemove", () => {
    const onRemove = vi.fn();
    render(<PersonaSamples persona={persona} canEdit violations={[]} onAdd={vi.fn()} onRemove={onRemove} />);
    expect(screen.getByText("200 words")).toBeInTheDocument();
    expect(screen.getByText("Some prose that goes on…")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Remove" }));
    expect(onRemove).toHaveBeenCalledWith("s1");
  });

  it("hides the add form and remove buttons when canEdit is false", () => {
    render(<PersonaSamples persona={persona} canEdit={false} violations={[]} onAdd={vi.fn()} onRemove={vi.fn()} />);
    expect(screen.queryByPlaceholderText(/Paste a writing sample/)).toBeNull();
    expect(screen.queryByRole("button", { name: "Remove" })).toBeNull();
  });
});
