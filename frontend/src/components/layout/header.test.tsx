import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Header } from "./header";

describe("Header", () => {
  it("renders title and subtitle", () => {
    render(<Header title="Dashboard" subtitle="Monitor your pipeline." />);
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    expect(screen.getByText("Monitor your pipeline.")).toBeInTheDocument();
  });

  it("renders action buttons when provided", () => {
    render(
      <Header title="Dashboard" subtitle="Sub">
        <button>New Scan</button>
      </Header>
    );
    expect(screen.getByText("New Scan")).toBeInTheDocument();
  });
});
