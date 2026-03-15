import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { DomainBadge } from "./domain-badge";

describe("DomainBadge", () => {
  it("renders domain label in uppercase", () => {
    render(<DomainBadge domain="cybersecurity" />);
    expect(screen.getByText("Cybersecurity")).toBeInTheDocument();
  });
  it("renders AI/ML label correctly", () => {
    render(<DomainBadge domain="ai-ml" />);
    expect(screen.getByText("AI / ML")).toBeInTheDocument();
  });
  it("renders unknown domain as-is", () => {
    render(<DomainBadge domain="fintech" />);
    expect(screen.getByText("fintech")).toBeInTheDocument();
  });
});
