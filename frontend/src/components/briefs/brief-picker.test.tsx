import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { BriefPicker, NEW_BRIEF } from "./brief-picker";
import type { Brief } from "@/types/brief";

const briefs: Brief[] = [
  {
    id: "b1",
    owner_id: "u",
    name: "Security explainer",
    keywords: [],
    content_type: "article",
    length_target: "medium",
    structural_diagram_mode: "illustration",
    require_outline_approval: false,
    created_at: "",
    updated_at: "",
  },
];

describe("BriefPicker", () => {
  it("lists New brief first and saved briefs by name", () => {
    render(<BriefPicker briefs={briefs} value={NEW_BRIEF} onChange={vi.fn()} />);
    const options = screen.getAllByRole("option");
    expect(options[0]).toHaveTextContent("New brief");
    expect(options[1]).toHaveTextContent("Security explainer");
  });

  it("calls onChange with the brief id", () => {
    const onChange = vi.fn();
    render(<BriefPicker briefs={briefs} value={NEW_BRIEF} onChange={onChange} />);
    fireEvent.change(screen.getByLabelText("Brief"), { target: { value: "b1" } });
    expect(onChange).toHaveBeenCalledWith("b1");
  });

  it("disables the select while loading", () => {
    render(<BriefPicker briefs={[]} value={NEW_BRIEF} onChange={vi.fn()} isLoading />);
    expect(screen.getByLabelText("Brief")).toBeDisabled();
  });
});
