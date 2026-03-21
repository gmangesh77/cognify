import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { DomainCard } from "./domain-card";
import type { DomainConfig } from "@/types/settings";

const mockDomain: DomainConfig = {
  id: "dom-1",
  name: "Cybersecurity",
  status: "active",
  trendSources: ["google_trends", "reddit", "hackernews"],
  keywords: ["security", "threats", "CVE"],
  articleCount: 24,
};

describe("DomainCard", () => {
  it("renders domain name", () => {
    render(<DomainCard domain={mockDomain} onEdit={vi.fn()} />);
    expect(screen.getByText("Cybersecurity")).toBeInTheDocument();
  });

  it("renders status badge", () => {
    render(<DomainCard domain={mockDomain} onEdit={vi.fn()} />);
    expect(screen.getByText("Active")).toBeInTheDocument();
  });

  it("renders trend source count", () => {
    render(<DomainCard domain={mockDomain} onEdit={vi.fn()} />);
    expect(screen.getByText("3 sources")).toBeInTheDocument();
  });

  it("renders keyword count", () => {
    render(<DomainCard domain={mockDomain} onEdit={vi.fn()} />);
    expect(screen.getByText("3 keywords")).toBeInTheDocument();
  });

  it("renders article count", () => {
    render(<DomainCard domain={mockDomain} onEdit={vi.fn()} />);
    expect(screen.getByText("24 articles")).toBeInTheDocument();
  });

  it("applies active border styling", () => {
    const { container } = render(<DomainCard domain={mockDomain} onEdit={vi.fn()} />);
    expect(container.firstChild).toHaveClass("border-primary");
  });

  it("calls onEdit when Edit is clicked", () => {
    const handler = vi.fn();
    render(<DomainCard domain={mockDomain} onEdit={handler} />);
    fireEvent.click(screen.getByText("Edit"));
    expect(handler).toHaveBeenCalledWith(mockDomain);
  });
});
