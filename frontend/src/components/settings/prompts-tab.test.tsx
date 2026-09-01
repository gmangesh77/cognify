import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { PromptsTab } from "./prompts-tab";
import type { PromptView } from "@/types/prompts";

const base: PromptView = {
  key: "content_outline.user", step: "content_outline", description: "Outline user turn",
  variables: ["title", "domain"], default_template: "D", template: "D",
  is_overridden: false, updated_by: null, updated_at: null,
};
const overridden: PromptView = {
  ...base, key: "content_seo.user", step: "content_seo", is_overridden: true, template: "X",
  variables: ["meta_description"],
};

describe("PromptsTab", () => {
  it("groups by step, shows variables and the Overridden badge", () => {
    render(<PromptsTab prompts={[base, overridden]} selectedKey={null} onSelect={vi.fn()} />);
    expect(screen.getByText("content_outline")).toBeInTheDocument();
    expect(screen.getByText("content_seo")).toBeInTheDocument();
    expect(screen.getByText("{title}")).toBeInTheDocument();
    expect(screen.getAllByText("Overridden")).toHaveLength(1);
  });

  it("selects a prompt on click", () => {
    const onSelect = vi.fn();
    render(<PromptsTab prompts={[base]} selectedKey={null} onSelect={onSelect} />);
    fireEvent.click(screen.getByText("content_outline.user"));
    expect(onSelect).toHaveBeenCalledWith("content_outline.user");
  });
});
