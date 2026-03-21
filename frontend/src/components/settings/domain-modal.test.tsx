import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { DomainModal } from "./domain-modal";
import type { DomainConfig } from "@/types/settings";

const mockDomain: DomainConfig = {
  id: "dom-1",
  name: "Cybersecurity",
  status: "active",
  trendSources: ["google_trends", "reddit"],
  keywords: ["security", "threats"],
  articleCount: 24,
};

describe("DomainModal", () => {
  it("renders nothing when open is false", () => {
    const { container } = render(
      <DomainModal domain={null} open={false} onClose={vi.fn()} onSubmit={vi.fn()} />
    );
    expect(container.innerHTML).toBe("");
  });

  it("renders Add Domain title when domain is null", () => {
    render(<DomainModal domain={null} open={true} onClose={vi.fn()} onSubmit={vi.fn()} />);
    expect(screen.getByText("Add Domain")).toBeInTheDocument();
  });

  it("renders Edit Domain title when domain is provided", () => {
    render(
      <DomainModal domain={mockDomain} open={true} onClose={vi.fn()} onSubmit={vi.fn()} />
    );
    expect(screen.getByText("Edit Domain")).toBeInTheDocument();
  });

  it("pre-fills form when editing", () => {
    render(
      <DomainModal domain={mockDomain} open={true} onClose={vi.fn()} onSubmit={vi.fn()} />
    );
    expect(screen.getByDisplayValue("Cybersecurity")).toBeInTheDocument();
    expect(screen.getByDisplayValue("security, threats")).toBeInTheDocument();
  });

  it("calls onClose when Cancel is clicked", () => {
    const handleClose = vi.fn();
    render(<DomainModal domain={null} open={true} onClose={handleClose} onSubmit={vi.fn()} />);
    fireEvent.click(screen.getByText("Cancel"));
    expect(handleClose).toHaveBeenCalled();
  });

  it("calls onSubmit with save action when Save is clicked", () => {
    const handleSubmit = vi.fn();
    render(
      <DomainModal domain={null} open={true} onClose={vi.fn()} onSubmit={handleSubmit} />
    );
    fireEvent.change(screen.getByLabelText("Domain Name"), {
      target: { value: "New Domain" },
    });
    fireEvent.click(screen.getByText("Save Domain"));
    expect(handleSubmit).toHaveBeenCalledWith(
      expect.objectContaining({ type: "save" })
    );
  });

  it("shows delete button only in edit mode", () => {
    const { rerender } = render(
      <DomainModal domain={null} open={true} onClose={vi.fn()} onSubmit={vi.fn()} />
    );
    expect(screen.queryByText("Delete Domain")).not.toBeInTheDocument();
    rerender(
      <DomainModal domain={mockDomain} open={true} onClose={vi.fn()} onSubmit={vi.fn()} />
    );
    expect(screen.getByText("Delete Domain")).toBeInTheDocument();
  });

  it("shows confirmation before delete", () => {
    render(
      <DomainModal domain={mockDomain} open={true} onClose={vi.fn()} onSubmit={vi.fn()} />
    );
    fireEvent.click(screen.getByText("Delete Domain"));
    expect(screen.getByText("Are you sure? This cannot be undone.")).toBeInTheDocument();
  });

  it("calls onSubmit with delete action after confirmation", () => {
    const handleSubmit = vi.fn();
    render(
      <DomainModal domain={mockDomain} open={true} onClose={vi.fn()} onSubmit={handleSubmit} />
    );
    fireEvent.click(screen.getByText("Delete Domain"));
    fireEvent.click(screen.getByText("Confirm Delete"));
    expect(handleSubmit).toHaveBeenCalledWith({ type: "delete", id: "dom-1" });
  });

  it("renders trend source checkboxes", () => {
    render(<DomainModal domain={null} open={true} onClose={vi.fn()} onSubmit={vi.fn()} />);
    expect(screen.getByLabelText("Google Trends")).toBeInTheDocument();
    expect(screen.getByLabelText("Reddit")).toBeInTheDocument();
    expect(screen.getByLabelText("Hacker News")).toBeInTheDocument();
    expect(screen.getByLabelText("NewsAPI")).toBeInTheDocument();
    expect(screen.getByLabelText("arXiv")).toBeInTheDocument();
  });
});
