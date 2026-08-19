import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ReviewOutlineCheckbox } from "./review-outline-checkbox";

describe("ReviewOutlineCheckbox", () => {
  it("renders the 'Review outline before drafting' label", () => {
    render(<ReviewOutlineCheckbox checked={false} onChange={() => {}} />);
    expect(screen.getByLabelText(/review outline before drafting/i)).toBeInTheDocument();
  });

  it("reflects the checked prop", () => {
    render(<ReviewOutlineCheckbox checked={true} onChange={() => {}} />);
    expect(screen.getByLabelText(/review outline before drafting/i)).toBeChecked();
  });

  it("calls onChange(true) when toggled on", () => {
    const onChange = vi.fn();
    render(<ReviewOutlineCheckbox checked={false} onChange={onChange} />);
    fireEvent.click(screen.getByLabelText(/review outline before drafting/i));
    expect(onChange).toHaveBeenCalledWith(true);
  });

  it("calls onChange(false) when toggled off", () => {
    const onChange = vi.fn();
    render(<ReviewOutlineCheckbox checked={true} onChange={onChange} />);
    fireEvent.click(screen.getByLabelText(/review outline before drafting/i));
    expect(onChange).toHaveBeenCalledWith(false);
  });
});
