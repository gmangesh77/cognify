import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ApiKeyRow } from "./api-key-row";
import type { ApiKeyConfig } from "@/types/settings";

const mockKey: ApiKeyConfig = {
  id: "key-1",
  service: "anthropic",
  maskedKey: "sk-ant-••••••••7f3a",
  status: "active",
};

describe("ApiKeyRow", () => {
  it("renders service name", () => {
    render(<ApiKeyRow apiKey={mockKey} onRotate={vi.fn()} />);
    expect(screen.getByText("Anthropic API")).toBeInTheDocument();
  });

  it("renders masked key", () => {
    render(<ApiKeyRow apiKey={mockKey} onRotate={vi.fn()} />);
    expect(screen.getByText("sk-ant-••••••••7f3a")).toBeInTheDocument();
  });

  it("renders status badge", () => {
    render(<ApiKeyRow apiKey={mockKey} onRotate={vi.fn()} />);
    expect(screen.getByText("Active")).toBeInTheDocument();
  });

  it("shows confirmation on first Rotate click", () => {
    render(<ApiKeyRow apiKey={mockKey} onRotate={vi.fn()} />);
    fireEvent.click(screen.getByText("Rotate"));
    expect(screen.getByText("Are you sure you want to rotate this key?")).toBeInTheDocument();
  });

  it("shows new key input after confirming rotation", () => {
    render(<ApiKeyRow apiKey={mockKey} onRotate={vi.fn()} />);
    fireEvent.click(screen.getByText("Rotate"));
    fireEvent.click(screen.getByText("Confirm"));
    expect(screen.getByPlaceholderText("New API key")).toBeInTheDocument();
  });

  it("calls onRotate with new key after entering it", () => {
    const handler = vi.fn();
    render(<ApiKeyRow apiKey={mockKey} onRotate={handler} />);
    fireEvent.click(screen.getByText("Rotate"));
    fireEvent.click(screen.getByText("Confirm"));
    fireEvent.change(screen.getByPlaceholderText("New API key"), {
      target: { value: "new-key-123" },
    });
    fireEvent.click(screen.getByText("Save"));
    expect(handler).toHaveBeenCalledWith("key-1", "new-key-123");
  });

  it("cancels at confirmation step", () => {
    render(<ApiKeyRow apiKey={mockKey} onRotate={vi.fn()} />);
    fireEvent.click(screen.getByText("Rotate"));
    fireEvent.click(screen.getByText("Cancel"));
    expect(screen.queryByText("Are you sure")).not.toBeInTheDocument();
  });
});
