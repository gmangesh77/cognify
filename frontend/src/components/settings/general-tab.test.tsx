import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { GeneralTab } from "./general-tab";
import type { GeneralConfig } from "@/types/settings";

const mockConfig: GeneralConfig = {
  articleLengthTarget: "3000-5000",
  contentTone: "professional",
  defaultAudiencePersona: "general_business",
};

describe("GeneralTab", () => {
  it("renders both dropdowns", () => {
    render(<GeneralTab config={mockConfig} onUpdate={vi.fn()} />);
    expect(screen.getByLabelText("Article Length Target")).toBeInTheDocument();
    expect(screen.getByLabelText("Content Tone")).toBeInTheDocument();
  });

  it("renders descriptions", () => {
    render(<GeneralTab config={mockConfig} onUpdate={vi.fn()} />);
    expect(screen.getByText(/Target word count/)).toBeInTheDocument();
    expect(screen.getByText(/Writing style/)).toBeInTheDocument();
  });

  it("calls onUpdate when article length changes", () => {
    const handler = vi.fn();
    render(<GeneralTab config={mockConfig} onUpdate={handler} />);
    fireEvent.change(screen.getByLabelText("Article Length Target"), {
      target: { value: "1000-2000" },
    });
    expect(handler).toHaveBeenCalledWith({ articleLengthTarget: "1000-2000" });
  });

  it("calls onUpdate when content tone changes", () => {
    const handler = vi.fn();
    render(<GeneralTab config={mockConfig} onUpdate={handler} />);
    fireEvent.change(screen.getByLabelText("Content Tone"), {
      target: { value: "casual" },
    });
    expect(handler).toHaveBeenCalledWith({ contentTone: "casual" });
  });

  it("renders the default audience persona selector", () => {
    render(<GeneralTab config={mockConfig} onUpdate={vi.fn()} />);
    const select = screen.getByLabelText(/Default audience persona/);
    expect(select).toBeInTheDocument();
    expect(select).toHaveValue("general_business");
  });

  it("calls onUpdate when persona changes", () => {
    const handler = vi.fn();
    render(<GeneralTab config={mockConfig} onUpdate={handler} />);
    fireEvent.change(screen.getByLabelText(/Default audience persona/), {
      target: { value: "cto" },
    });
    expect(handler).toHaveBeenCalledWith({ defaultAudiencePersona: "cto" });
  });
});
