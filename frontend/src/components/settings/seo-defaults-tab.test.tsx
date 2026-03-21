import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { SeoDefaultsTab } from "./seo-defaults-tab";
import type { SeoDefaults } from "@/types/settings";

const mockDefaults: SeoDefaults = {
  autoMetaTags: true,
  keywordOptimization: true,
  autoCoverImages: false,
  includeCitations: true,
  humanReviewBeforePublish: true,
};

describe("SeoDefaultsTab", () => {
  it("renders all 5 toggle labels", () => {
    render(<SeoDefaultsTab defaults={mockDefaults} onToggle={vi.fn()} />);
    expect(screen.getByText("Auto-generate meta tags")).toBeInTheDocument();
    expect(screen.getByText("Keyword optimization")).toBeInTheDocument();
    expect(screen.getByText("Auto-generate cover images")).toBeInTheDocument();
    expect(screen.getByText("Include citations")).toBeInTheDocument();
    expect(screen.getByText("Human review before publish")).toBeInTheDocument();
  });

  it("renders description text", () => {
    render(<SeoDefaultsTab defaults={mockDefaults} onToggle={vi.fn()} />);
    expect(screen.getByText(/title and description meta tags/)).toBeInTheDocument();
  });

  it("renders correct toggle states", () => {
    render(<SeoDefaultsTab defaults={mockDefaults} onToggle={vi.fn()} />);
    const switches = screen.getAllByRole("switch");
    expect(switches[0]).toHaveAttribute("aria-checked", "true");
    expect(switches[2]).toHaveAttribute("aria-checked", "false");
  });

  it("calls onToggle when switch is clicked", () => {
    const handler = vi.fn();
    render(<SeoDefaultsTab defaults={mockDefaults} onToggle={handler} />);
    const switches = screen.getAllByRole("switch");
    fireEvent.click(switches[0]);
    expect(handler).toHaveBeenCalledWith("autoMetaTags");
  });
});
