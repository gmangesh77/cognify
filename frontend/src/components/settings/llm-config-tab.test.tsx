import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { LlmConfigTab } from "./llm-config-tab";
import type { LlmConfig } from "@/types/settings";

const mockConfig: LlmConfig = {
  primaryModel: "claude-opus-4",
  draftingModel: "claude-sonnet-4",
  imageGeneration: "stable-diffusion-xl",
};

describe("LlmConfigTab", () => {
  it("renders all 3 dropdowns", () => {
    render(<LlmConfigTab config={mockConfig} onUpdate={vi.fn()} />);
    expect(screen.getByLabelText("Primary Model")).toBeInTheDocument();
    expect(screen.getByLabelText("Drafting Model")).toBeInTheDocument();
    expect(screen.getByLabelText("Image Generation")).toBeInTheDocument();
  });

  it("renders description text for each dropdown", () => {
    render(<LlmConfigTab config={mockConfig} onUpdate={vi.fn()} />);
    expect(screen.getByText(/final article synthesis/)).toBeInTheDocument();
    expect(screen.getByText(/section drafting/)).toBeInTheDocument();
    expect(screen.getByText(/hero images/)).toBeInTheDocument();
  });

  it("calls onUpdate when primary model changes", () => {
    const handler = vi.fn();
    render(<LlmConfigTab config={mockConfig} onUpdate={handler} />);
    fireEvent.change(screen.getByLabelText("Primary Model"), {
      target: { value: "claude-sonnet-4" },
    });
    expect(handler).toHaveBeenCalledWith({ primaryModel: "claude-sonnet-4" });
  });
});
