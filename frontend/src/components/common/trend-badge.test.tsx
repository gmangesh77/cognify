import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { TrendBadge } from "./trend-badge";

describe("TrendBadge", () => {
  it("renders trending variant with correct text", () => {
    render(<TrendBadge variant="trending" />);
    expect(screen.getByText("Trending")).toBeInTheDocument();
  });
  it("renders new variant", () => {
    render(<TrendBadge variant="new" />);
    expect(screen.getByText("New")).toBeInTheDocument();
  });
  it("renders rising variant", () => {
    render(<TrendBadge variant="rising" />);
    expect(screen.getByText("Rising")).toBeInTheDocument();
  });
  it("renders steady variant", () => {
    render(<TrendBadge variant="steady" />);
    expect(screen.getByText("Steady")).toBeInTheDocument();
  });
});
