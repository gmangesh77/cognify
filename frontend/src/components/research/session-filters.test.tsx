import { render, screen, fireEvent } from "@testing-library/react";
import { SessionFilters } from "./session-filters";

describe("SessionFilters", () => {
  it("renders all 5 filter tabs", () => {
    render(<SessionFilters activeFilter="all" onFilterChange={() => {}} totalCount={8} />);
    expect(screen.getByText("All")).toBeInTheDocument();
    expect(screen.getByText("Planning")).toBeInTheDocument();
    expect(screen.getByText("In Progress")).toBeInTheDocument();
    expect(screen.getByText("Complete")).toBeInTheDocument();
    expect(screen.getByText("Failed")).toBeInTheDocument();
  });

  it("shows total count", () => {
    render(<SessionFilters activeFilter="all" onFilterChange={() => {}} totalCount={8} />);
    expect(screen.getByText("8 Sessions")).toBeInTheDocument();
  });

  it("calls onFilterChange with correct value", () => {
    const onChange = vi.fn();
    render(<SessionFilters activeFilter="all" onFilterChange={onChange} totalCount={8} />);
    fireEvent.click(screen.getByText("Complete"));
    expect(onChange).toHaveBeenCalledWith("complete");
  });

  it("highlights active filter", () => {
    render(<SessionFilters activeFilter="complete" onFilterChange={() => {}} totalCount={4} />);
    const completeBtn = screen.getByText("Complete");
    expect(completeBtn.className).toContain("bg-primary");
  });
});
