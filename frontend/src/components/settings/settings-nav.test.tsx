import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { SettingsNav } from "./settings-nav";

describe("SettingsNav", () => {
  it("renders all 5 tab items", () => {
    render(<SettingsNav activeTab="domains" onTabChange={vi.fn()} />);
    expect(screen.getByText("Domains")).toBeInTheDocument();
    expect(screen.getByText("LLM Configuration")).toBeInTheDocument();
    expect(screen.getByText("API Keys")).toBeInTheDocument();
    expect(screen.getByText("SEO Defaults")).toBeInTheDocument();
    expect(screen.getByText("General")).toBeInTheDocument();
  });

  it("highlights the active tab", () => {
    render(<SettingsNav activeTab="llm" onTabChange={vi.fn()} />);
    const activeButton = screen.getByText("LLM Configuration");
    expect(activeButton.closest("button")).toHaveClass("bg-primary/10");
  });

  it("calls onTabChange when a tab is clicked", () => {
    const handler = vi.fn();
    render(<SettingsNav activeTab="domains" onTabChange={handler} />);
    fireEvent.click(screen.getByText("API Keys"));
    expect(handler).toHaveBeenCalledWith("api-keys");
  });
});
