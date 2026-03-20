import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { FilterBar } from "./filter-bar";
import type { TopicFilters } from "@/types/api";

const defaultFilters: TopicFilters = { sources: [], timeRange: "7d", domain: "" };

describe("FilterBar", () => {
  it("renders topic count", () => {
    render(<FilterBar filters={defaultFilters} onFilterChange={vi.fn()} topicCount={42} />);
    expect(screen.getByText("42 Topics Found")).toBeInTheDocument();
  });
  it("shows All Sources when no sources selected", () => {
    render(<FilterBar filters={defaultFilters} onFilterChange={vi.fn()} topicCount={0} />);
    expect(screen.getByText("All Sources")).toBeInTheDocument();
  });
  it("shows domain selector with All Domains default", () => {
    render(<FilterBar filters={defaultFilters} onFilterChange={vi.fn()} topicCount={0} />);
    expect(screen.getByText("All Domains")).toBeInTheDocument();
  });
  it("calls onFilterChange when domain changes", () => {
    const handler = vi.fn();
    render(<FilterBar filters={defaultFilters} onFilterChange={handler} topicCount={0} />);
    fireEvent.change(screen.getByDisplayValue("All Domains"), { target: { value: "cybersecurity" } });
    expect(handler).toHaveBeenCalledWith({ domain: "cybersecurity" });
  });
  it("calls onFilterChange when time range changes", () => {
    const handler = vi.fn();
    render(<FilterBar filters={defaultFilters} onFilterChange={handler} topicCount={0} />);
    fireEvent.change(screen.getByDisplayValue("Last 7 Days"), { target: { value: "24h" } });
    expect(handler).toHaveBeenCalledWith({ timeRange: "24h" });
  });
  it("toggles source selection in multi-select", () => {
    const handler = vi.fn();
    render(<FilterBar filters={defaultFilters} onFilterChange={handler} topicCount={0} />);
    fireEvent.click(screen.getByText("All Sources"));
    fireEvent.click(screen.getByText("Reddit"));
    expect(handler).toHaveBeenCalledWith({ sources: ["reddit"] });
  });
});
