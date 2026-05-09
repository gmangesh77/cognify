import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { VisualsTab } from "./visuals-tab";
import type { LlmConfig } from "@/types/settings";

const BASE_CONFIG: LlmConfig = {
  primaryModel: "claude-opus-4",
  draftingModel: "claude-sonnet-4",
  imageGeneration: "stable-diffusion-xl",
  imageProvider: "dalle_3",
  imageModel: null,
};

describe("VisualsTab", () => {
  it("defaults provider to DALL·E 3 and shows OpenAI credential hint", () => {
    render(<VisualsTab config={BASE_CONFIG} onUpdate={vi.fn()} />);
    const select = screen.getByLabelText(/provider/i) as HTMLSelectElement;
    expect(select.value).toBe("dalle_3");
    expect(screen.getByText(/DALL·E 3 needs an/)).toBeInTheDocument();
  });

  it("changes the credential hint when switching to a Google provider", () => {
    const onUpdate = vi.fn();
    render(<VisualsTab config={BASE_CONFIG} onUpdate={onUpdate} />);
    fireEvent.change(screen.getByLabelText(/provider/i), {
      target: { value: "gemini_flash" },
    });
    expect(onUpdate).toHaveBeenCalledWith(
      expect.objectContaining({
        imageProvider: "gemini_flash",
        imageModel: null,
      }),
    );
  });

  it("emits the chosen model on change", () => {
    const onUpdate = vi.fn();
    render(
      <VisualsTab
        config={{ ...BASE_CONFIG, imageProvider: "gemini_flash" }}
        onUpdate={onUpdate}
      />,
    );
    fireEvent.change(screen.getByLabelText(/model/i), {
      target: { value: "gemini-2.5-flash-image" },
    });
    expect(onUpdate).toHaveBeenCalledWith({
      imageModel: "gemini-2.5-flash-image",
    });
  });

  it("emits null when 'Provider default' is selected", () => {
    const onUpdate = vi.fn();
    render(
      <VisualsTab
        config={{ ...BASE_CONFIG, imageModel: "dall-e-3" }}
        onUpdate={onUpdate}
      />,
    );
    fireEvent.change(screen.getByLabelText(/model/i), {
      target: { value: "" },
    });
    expect(onUpdate).toHaveBeenCalledWith({ imageModel: null });
  });

  it("does not list Anthropic as a provider option", () => {
    render(<VisualsTab config={BASE_CONFIG} onUpdate={vi.fn()} />);
    const select = screen.getByLabelText(/provider/i) as HTMLSelectElement;
    const options = Array.from(select.options).map((o) => o.value);
    expect(options).not.toContain("anthropic");
    expect(options).not.toContain("claude");
  });
});
