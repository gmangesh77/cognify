import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MermaidDiagram } from "./mermaid-diagram";

const mockInitialize = vi.fn();
const mockRender = vi.fn();

vi.mock("mermaid", () => ({
  default: {
    initialize: (...args: unknown[]) => mockInitialize(...args),
    render: (...args: unknown[]) => mockRender(...args),
  },
}));

describe("MermaidDiagram", () => {
  beforeEach(() => {
    mockInitialize.mockReset();
    mockRender.mockReset();
    mockRender.mockResolvedValue({
      svg: "<svg data-testid='mermaid-svg'><g>rendered</g></svg>",
    });
  });

  it("initializes mermaid once with strict security settings", async () => {
    render(
      <MermaidDiagram
        syntax={"graph TD\n  A --> B"}
        caption="Test"
        altText="Diagram"
      />,
    );
    await waitFor(() => expect(mockInitialize).toHaveBeenCalled());
    const opts = mockInitialize.mock.calls[0][0];
    expect(opts.securityLevel).toBe("strict");
    expect(opts.startOnLoad).toBe(false);
  });

  it("calls mermaid.render with the provided syntax", async () => {
    render(
      <MermaidDiagram
        syntax={"graph TD\n  A --> B"}
        caption="Test"
        altText="Diagram"
      />,
    );
    await waitFor(() => expect(mockRender).toHaveBeenCalled());
    const callArgs = mockRender.mock.calls[0];
    expect(callArgs[1]).toBe("graph TD\n  A --> B");
  });

  it("injects the rendered SVG into the DOM", async () => {
    render(
      <MermaidDiagram
        syntax={"graph TD\n  A --> B"}
        caption="Flow"
        altText="Flow"
      />,
    );
    await waitFor(() => {
      expect(screen.getByTestId("mermaid-svg")).toBeInTheDocument();
    });
  });

  it("renders the caption beneath the diagram", async () => {
    render(
      <MermaidDiagram
        syntax={"graph TD\n  A --> B"}
        caption="Authentication flow overview."
        altText="Auth"
      />,
    );
    expect(
      screen.getByText("Authentication flow overview."),
    ).toBeInTheDocument();
  });

  it("falls back to PNG when mermaid render throws", async () => {
    mockRender.mockRejectedValueOnce(new Error("parse error"));
    render(
      <MermaidDiagram
        syntax="invalid"
        caption="Broken"
        altText="Broken"
        fallbackUrl="/assets/broken.png"
      />,
    );
    await waitFor(() => {
      const img = screen.getByAltText("Broken") as HTMLImageElement;
      expect(img.src).toContain("/assets/broken.png");
    });
  });

  it("shows a neutral placeholder when render fails with no fallback", async () => {
    mockRender.mockRejectedValueOnce(new Error("parse error"));
    render(
      <MermaidDiagram syntax="invalid" caption="Broken" altText="Broken" />,
    );
    await waitFor(() => {
      expect(
        screen.getByText(/diagram could not be rendered/i),
      ).toBeInTheDocument();
    });
  });
});
