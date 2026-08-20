import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { BriefOptionsFields, type BriefOptions } from "./brief-options-fields";

const base: BriefOptions = { content_type: "article", length_target: "medium", save_as_brief: false, brief_name: "" };

describe("BriefOptionsFields", () => {
  it("emits content type and length changes", () => {
    const onChange = vi.fn();
    render(<BriefOptionsFields value={base} onChange={onChange} showSave />);
    fireEvent.change(screen.getByLabelText("Content type"), { target: { value: "how-to" } });
    expect(onChange).toHaveBeenCalledWith({ ...base, content_type: "how-to" });
    fireEvent.change(screen.getByLabelText("Length"), { target: { value: "long" } });
    expect(onChange).toHaveBeenCalledWith({ ...base, length_target: "long" });
  });

  it("shows the name input only when save-as-brief is checked", () => {
    const onChange = vi.fn();
    const { rerender } = render(<BriefOptionsFields value={base} onChange={onChange} showSave />);
    expect(screen.queryByLabelText("Brief name")).toBeNull();
    fireEvent.click(screen.getByLabelText("Save as brief"));
    expect(onChange).toHaveBeenCalledWith({ ...base, save_as_brief: true });
    rerender(<BriefOptionsFields value={{ ...base, save_as_brief: true }} onChange={onChange} showSave />);
    expect(screen.getByLabelText("Brief name")).toBeInTheDocument();
  });

  it("hides save controls when showSave is false", () => {
    render(<BriefOptionsFields value={base} onChange={vi.fn()} showSave={false} />);
    expect(screen.queryByLabelText("Save as brief")).toBeNull();
  });
});
