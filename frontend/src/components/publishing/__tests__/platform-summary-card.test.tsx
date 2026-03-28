import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { PlatformSummaryCard } from "../platform-summary-card";

describe("PlatformSummaryCard", () => {
  it("renders platform name and counts", () => {
    render(
      <PlatformSummaryCard
        summary={{ platform: "ghost", total: 10, success: 8, failed: 1, scheduled: 1 }}
      />,
    );
    expect(screen.getByText("Ghost")).toBeInTheDocument();
    expect(screen.getByText("10")).toBeInTheDocument();
    expect(screen.getByText("8 live")).toBeInTheDocument();
    expect(screen.getByText("1 failed")).toBeInTheDocument();
  });

  it("capitalizes platform name", () => {
    render(
      <PlatformSummaryCard
        summary={{ platform: "medium", total: 3, success: 2, failed: 1, scheduled: 0 }}
      />,
    );
    expect(screen.getByText("Medium")).toBeInTheDocument();
  });
});
