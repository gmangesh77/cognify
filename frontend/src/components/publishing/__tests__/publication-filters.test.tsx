import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { PublicationFilters } from "../publication-filters";

describe("PublicationFilters", () => {
  it("renders all status filter pills", () => {
    render(
      <PublicationFilters
        activePlatform="all"
        activeStatus="all"
        onPlatformChange={vi.fn()}
        onStatusChange={vi.fn()}
        totalCount={5}
      />,
    );
    expect(screen.getByText("Live")).toBeInTheDocument();
    expect(screen.getByText("Failed")).toBeInTheDocument();
    expect(screen.getByText("Scheduled")).toBeInTheDocument();
  });

  it("calls onStatusChange when a status pill is clicked", () => {
    const onStatusChange = vi.fn();
    render(
      <PublicationFilters
        activePlatform="all"
        activeStatus="all"
        onPlatformChange={vi.fn()}
        onStatusChange={onStatusChange}
        totalCount={5}
      />,
    );
    fireEvent.click(screen.getByText("Failed"));
    expect(onStatusChange).toHaveBeenCalledWith("failed");
  });

  it("shows total count", () => {
    render(
      <PublicationFilters
        activePlatform="all"
        activeStatus="all"
        onPlatformChange={vi.fn()}
        onStatusChange={vi.fn()}
        totalCount={42}
      />,
    );
    expect(screen.getByText("42 Publications")).toBeInTheDocument();
  });
});
