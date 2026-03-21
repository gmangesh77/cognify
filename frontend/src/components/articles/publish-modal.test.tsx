import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { PublishModal } from "./publish-modal";

describe("PublishModal", () => {
  it("renders nothing when open is false", () => {
    const { container } = render(
      <PublishModal open={false} onClose={vi.fn()} onPublish={vi.fn()} />
    );
    expect(container.innerHTML).toBe("");
  });

  it("renders modal title when open", () => {
    render(<PublishModal open={true} onClose={vi.fn()} onPublish={vi.fn()} />);
    expect(screen.getByText("Publish Article")).toBeInTheDocument();
  });

  it("renders all 4 platform checkboxes", () => {
    render(<PublishModal open={true} onClose={vi.fn()} onPublish={vi.fn()} />);
    expect(screen.getByLabelText("Ghost")).toBeInTheDocument();
    expect(screen.getByLabelText("WordPress")).toBeInTheDocument();
    expect(screen.getByLabelText("Medium")).toBeInTheDocument();
    expect(screen.getByLabelText("LinkedIn")).toBeInTheDocument();
  });

  it("publish button disabled when no platforms selected", () => {
    render(<PublishModal open={true} onClose={vi.fn()} onPublish={vi.fn()} />);
    expect(screen.getByText("Publish")).toBeDisabled();
  });

  it("publish button enabled after selecting a platform", () => {
    render(<PublishModal open={true} onClose={vi.fn()} onPublish={vi.fn()} />);
    fireEvent.click(screen.getByLabelText("Ghost"));
    expect(screen.getByText("Publish")).not.toBeDisabled();
  });

  it("calls onPublish with selected platforms", () => {
    const handler = vi.fn();
    render(<PublishModal open={true} onClose={vi.fn()} onPublish={handler} />);
    fireEvent.click(screen.getByLabelText("Ghost"));
    fireEvent.click(screen.getByLabelText("Medium"));
    fireEvent.click(screen.getByText("Publish"));
    expect(handler).toHaveBeenCalledWith(["ghost", "medium"]);
  });

  it("calls onClose when Cancel is clicked", () => {
    const handleClose = vi.fn();
    render(<PublishModal open={true} onClose={handleClose} onPublish={vi.fn()} />);
    fireEvent.click(screen.getByText("Cancel"));
    expect(handleClose).toHaveBeenCalled();
  });
});
