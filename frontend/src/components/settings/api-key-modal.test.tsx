import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ApiKeyModal } from "./api-key-modal";

describe("ApiKeyModal", () => {
  it("renders nothing when open is false", () => {
    const { container } = render(
      <ApiKeyModal open={false} onSave={vi.fn()} onClose={vi.fn()} />
    );
    expect(container.innerHTML).toBe("");
  });

  it("renders form when open", () => {
    render(<ApiKeyModal open={true} onSave={vi.fn()} onClose={vi.fn()} />);
    expect(screen.getByText("Add API Key")).toBeInTheDocument();
    expect(screen.getByLabelText("Service")).toBeInTheDocument();
    expect(screen.getByLabelText("API Key")).toBeInTheDocument();
  });

  it("calls onSave with service and key", () => {
    const handleSave = vi.fn();
    render(<ApiKeyModal open={true} onSave={handleSave} onClose={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("Service"), {
      target: { value: "serpapi" },
    });
    fireEvent.change(screen.getByLabelText("API Key"), {
      target: { value: "serp-my-key" },
    });
    fireEvent.click(screen.getByText("Save"));
    expect(handleSave).toHaveBeenCalledWith("serpapi", "serp-my-key");
  });

  it("calls onClose when Cancel is clicked", () => {
    const handleClose = vi.fn();
    render(<ApiKeyModal open={true} onSave={vi.fn()} onClose={handleClose} />);
    fireEvent.click(screen.getByText("Cancel"));
    expect(handleClose).toHaveBeenCalled();
  });

  it("toggles API key visibility", () => {
    render(<ApiKeyModal open={true} onSave={vi.fn()} onClose={vi.fn()} />);
    const keyInput = screen.getByLabelText("API Key");
    expect(keyInput).toHaveAttribute("type", "password");
    fireEvent.click(screen.getByLabelText("Toggle key visibility"));
    expect(keyInput).toHaveAttribute("type", "text");
  });
});
