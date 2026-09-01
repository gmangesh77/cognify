import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { PromptEditor } from "./prompt-editor";
import type { PromptView } from "@/types/prompts";

const prompt: PromptView = {
  key: "content_outline.user", step: "content_outline", description: "d",
  variables: ["title"], default_template: "Default {title}", template: "Default {title}",
  is_overridden: false, updated_by: null, updated_at: null,
};

describe("PromptEditor", () => {
  it("disables Save until the template changes, then saves", () => {
    const onSave = vi.fn();
    render(<PromptEditor prompt={prompt} canEdit violations={[]} saving={false} onSave={onSave} onReset={vi.fn()} />);
    const save = screen.getByRole("button", { name: "Save" });
    expect(save).toBeDisabled();
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "New {title}" } });
    fireEvent.click(save);
    expect(onSave).toHaveBeenCalledWith("New {title}");
  });

  it("shows Reset only when overridden and renders violations", () => {
    render(
      <PromptEditor prompt={{ ...prompt, is_overridden: true, template: "X {title}" }} canEdit
        violations={["unknown variable {bogus}"]} saving={false} onSave={vi.fn()} onReset={vi.fn()} />,
    );
    expect(screen.getByRole("button", { name: "Reset to default" })).toBeInTheDocument();
    expect(screen.getByText("unknown variable {bogus}")).toBeInTheDocument();
  });

  it("is read-only for non-admins", () => {
    render(<PromptEditor prompt={prompt} canEdit={false} violations={[]} saving={false} onSave={vi.fn()} onReset={vi.fn()} />);
    expect(screen.getByRole("textbox")).toHaveAttribute("readonly");
    expect(screen.queryByRole("button", { name: "Save" })).toBeNull();
    expect(screen.getByText(/Only admins can edit prompts/)).toBeInTheDocument();
  });
});
