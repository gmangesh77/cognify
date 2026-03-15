import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MetricCard } from "./metric-card";

describe("MetricCard", () => {
  it("renders label and value", () => {
    render(<MetricCard label="Topics Discovered" value="147" trend={12} trendDirection="up" />);
    expect(screen.getByText("Topics Discovered")).toBeInTheDocument();
    expect(screen.getByText("147")).toBeInTheDocument();
  });

  it("shows positive trend with up arrow", () => {
    render(<MetricCard label="Published" value="24" trend={8} trendDirection="up" />);
    expect(screen.getByText("+8%")).toBeInTheDocument();
  });

  it("shows negative trend as positive when direction matches positive", () => {
    render(
      <MetricCard label="Avg Research Time" value="4.2m" trend={15} trendDirection="down" positiveDirection="down" />
    );
    expect(screen.getByText("-15%")).toBeInTheDocument();
  });
});
