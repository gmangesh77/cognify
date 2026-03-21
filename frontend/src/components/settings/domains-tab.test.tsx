import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { DomainsTab } from "./domains-tab";
import type { DomainConfig } from "@/types/settings";

const mockDomains: DomainConfig[] = [
  {
    id: "dom-1", name: "Cybersecurity", status: "active",
    trendSources: ["google_trends", "reddit"], keywords: ["security"], articleCount: 24,
  },
  {
    id: "dom-2", name: "AI & ML", status: "inactive",
    trendSources: ["arxiv"], keywords: ["LLM"], articleCount: 7,
  },
];

const actions = { add: vi.fn(), update: vi.fn(), delete: vi.fn() };

describe("DomainsTab", () => {
  it("renders all domain cards", () => {
    render(<DomainsTab domains={mockDomains} actions={actions} />);
    expect(screen.getByText("Cybersecurity")).toBeInTheDocument();
    expect(screen.getByText("AI & ML")).toBeInTheDocument();
  });

  it("renders Add Domain button", () => {
    render(<DomainsTab domains={mockDomains} actions={actions} />);
    expect(screen.getByText("+ Add Domain")).toBeInTheDocument();
  });

  it("opens add modal when button clicked", () => {
    render(<DomainsTab domains={mockDomains} actions={actions} />);
    fireEvent.click(screen.getByText("+ Add Domain"));
    expect(screen.getByText("Add Domain")).toBeInTheDocument();
  });

  it("opens edit modal when Edit is clicked on a card", () => {
    render(<DomainsTab domains={mockDomains} actions={actions} />);
    fireEvent.click(screen.getAllByText("Edit")[0]);
    expect(screen.getByText("Edit Domain")).toBeInTheDocument();
  });

  it("shows empty state when no domains", () => {
    render(<DomainsTab domains={[]} actions={actions} />);
    expect(screen.getByText("No domains configured")).toBeInTheDocument();
  });
});
