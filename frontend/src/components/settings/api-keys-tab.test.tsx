import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ApiKeysTab } from "./api-keys-tab";
import type { ApiKeyConfig, ApiKeyService } from "@/types/settings";

const mockKeys: ApiKeyConfig[] = [
  { id: "key-1", service: "anthropic", maskedKey: "sk-ant-••••7f3a", status: "active" },
  { id: "key-2", service: "serpapi", maskedKey: "serp-••••2b1c", status: "active" },
];

const actions = {
  add: vi.fn() as (service: ApiKeyService, key: string) => void,
  rotate: vi.fn() as (id: string, newKey: string) => void,
};

describe("ApiKeysTab", () => {
  it("renders all key rows", () => {
    render(<ApiKeysTab apiKeys={mockKeys} actions={actions} />);
    expect(screen.getByText("Anthropic API")).toBeInTheDocument();
    expect(screen.getByText("SerpAPI")).toBeInTheDocument();
  });

  it("renders Add API Key button", () => {
    render(<ApiKeysTab apiKeys={mockKeys} actions={actions} />);
    expect(screen.getByText("+ Add API Key")).toBeInTheDocument();
  });

  it("opens add modal when button clicked", () => {
    render(<ApiKeysTab apiKeys={mockKeys} actions={actions} />);
    fireEvent.click(screen.getByText("+ Add API Key"));
    expect(screen.getByText("Add API Key")).toBeInTheDocument();
  });

  it("shows empty state when no keys", () => {
    render(<ApiKeysTab apiKeys={[]} actions={actions} />);
    expect(screen.getByText("No API keys configured")).toBeInTheDocument();
  });
});
