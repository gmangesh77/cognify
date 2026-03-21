import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatusBadge } from "./status-badge";

describe("StatusBadge", () => {
  it("renders live status", () => {
    render(<StatusBadge status="live" />);
    expect(screen.getByText("Live")).toBeInTheDocument();
  });
  it("renders draft status", () => {
    render(<StatusBadge status="draft" />);
    expect(screen.getByText("Draft")).toBeInTheDocument();
  });
  it("renders scheduled status", () => {
    render(<StatusBadge status="scheduled" />);
    expect(screen.getByText("Scheduled")).toBeInTheDocument();
  });
  it("renders failed status", () => {
    render(<StatusBadge status="failed" />);
    expect(screen.getByText("Failed")).toBeInTheDocument();
  });

  it("renders complete status", () => {
    render(<StatusBadge status="complete" />);
    expect(screen.getByText("Complete")).toBeInTheDocument();
  });

  it("renders published status", () => {
    render(<StatusBadge status="published" />);
    expect(screen.getByText("Published")).toBeInTheDocument();
  });
});
