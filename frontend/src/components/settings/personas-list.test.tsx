import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { PersonasList } from "./personas-list";
import type { PersonaSummary } from "@/types/persona";

const ready: PersonaSummary = {
  id: "p1",
  name: "House Style",
  description: null,
  sample_count: 5,
  ready: true,
  updated_at: "2026-09-01T00:00:00Z",
};

const notReady: PersonaSummary = {
  id: "p2",
  name: "Founder Voice",
  description: null,
  sample_count: 2,
  ready: false,
  updated_at: "2026-09-01T00:00:00Z",
};

describe("PersonasList", () => {
  it("shows each persona's name, sample count, and Ready/needs-more badge", () => {
    render(<PersonasList personas={[ready, notReady]} selectedId={null} onSelect={vi.fn()} onCreate={vi.fn()} />);
    expect(screen.getByText("House Style")).toBeInTheDocument();
    expect(screen.getByText("5 samples")).toBeInTheDocument();
    expect(screen.getByText("Ready")).toBeInTheDocument();
    expect(screen.getByText("Founder Voice")).toBeInTheDocument();
    expect(screen.getByText("2 samples")).toBeInTheDocument();
    expect(screen.getByText("needs 3 more")).toBeInTheDocument();
  });

  it("calls onSelect when a persona is clicked", () => {
    const onSelect = vi.fn();
    render(<PersonasList personas={[ready]} selectedId={null} onSelect={onSelect} onCreate={vi.fn()} />);
    fireEvent.click(screen.getByText("House Style"));
    expect(onSelect).toHaveBeenCalledWith("p1");
  });

  it("highlights the selected persona", () => {
    render(<PersonasList personas={[ready]} selectedId="p1" onSelect={vi.fn()} onCreate={vi.fn()} />);
    expect(screen.getByText("House Style").closest("button")).toHaveClass("bg-primary-light");
  });

  it("calls onCreate with the trimmed name and clears the input", () => {
    const onCreate = vi.fn();
    render(<PersonasList personas={[]} selectedId={null} onSelect={vi.fn()} onCreate={onCreate} />);
    const input = screen.getByPlaceholderText("New persona name");
    fireEvent.change(input, { target: { value: "  Brand Voice  " } });
    fireEvent.click(screen.getByRole("button", { name: "New persona" }));
    expect(onCreate).toHaveBeenCalledWith("Brand Voice");
    expect(input).toHaveValue("");
  });

  it("disables the create button until a name is entered", () => {
    render(<PersonasList personas={[]} selectedId={null} onSelect={vi.fn()} onCreate={vi.fn()} />);
    expect(screen.getByRole("button", { name: "New persona" })).toBeDisabled();
  });

  it("shows an empty state with no personas", () => {
    render(<PersonasList personas={[]} selectedId={null} onSelect={vi.fn()} onCreate={vi.fn()} />);
    expect(screen.getByText("No personas yet.")).toBeInTheDocument();
  });
});
