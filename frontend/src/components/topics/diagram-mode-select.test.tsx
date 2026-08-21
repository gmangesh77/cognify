import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { DiagramModeSelect } from "./diagram-mode-select";

describe("DiagramModeSelect", () => {
  it("renders both modes and emits changes", () => {
    const onChange = vi.fn();
    render(<DiagramModeSelect value="illustration" onChange={onChange} />);
    expect(screen.getAllByRole("option")).toHaveLength(2);
    fireEvent.change(screen.getByLabelText("Diagram style"), { target: { value: "mermaid" } });
    expect(onChange).toHaveBeenCalledWith("mermaid");
  });
});
