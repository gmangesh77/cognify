import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import { SpecCard } from "./SpecCard";
import type { ImageSpec, RenderResponse } from "@/types/visuals";

const baseSpec: ImageSpec = {
  id: "spec_1",
  role_style: "hero",
  visual_style: "lifestyle_photo",
  prompt: "A founder reviewing dashboards.",
  alt_text: "Founder",
  aspect_ratio: "16:9",
  placement: {
    anchor: "cover",
    heading_text: null,
    paragraph_index: null,
    section_index: -1,
  },
  rationale: null,
  provider: null,
};

const sampleRender: RenderResponse = {
  image_url: null,
  image_base64: "iVBOR=",
  spec_id: "spec_1",
  width: 1,
  height: 1,
  mime_type: "image/png",
  provider: "gemini_flash",
  model: "stub",
  cost_usd: 0,
  latency_ms: 1,
};

describe("SpecCard", () => {
  it("idle state renders the Plan visual CTA", () => {
    const onPlan = vi.fn();
    render(<SpecCard spec={baseSpec} state="idle" onPlan={onPlan} />);
    fireEvent.click(screen.getByText("Plan visual"));
    expect(onPlan).toHaveBeenCalled();
  });

  it("planning state shows the planning checklist", () => {
    render(<SpecCard spec={baseSpec} state="planning" />);
    expect(screen.getAllByText(/Planning/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/Reading section/i)).toBeInTheDocument();
    expect(screen.getByText(/Picking styles/i)).toBeInTheDocument();
  });

  it("generating state surfaces the ETA when supplied", () => {
    render(
      <SpecCard
        spec={baseSpec}
        state="generating"
        generationEta="seconds 3 of 6"
      />,
    );
    expect(screen.getByText(/Rendering pixels/)).toBeInTheDocument();
    expect(screen.getByText("seconds 3 of 6")).toBeInTheDocument();
  });

  it("done state renders the image and Regenerate / Edit actions", () => {
    const onRegenerate = vi.fn();
    const onEdit = vi.fn();
    render(
      <SpecCard
        spec={baseSpec}
        state="done"
        render={sampleRender}
        onRegenerate={onRegenerate}
        onEdit={onEdit}
      />,
    );
    const img = screen.getByRole("img");
    expect(img).toHaveAttribute("alt", "Founder");
    fireEvent.click(screen.getByText("Regenerate"));
    fireEvent.click(screen.getByText("Edit"));
    expect(onRegenerate).toHaveBeenCalled();
    expect(onEdit).toHaveBeenCalled();
  });

  it("error state shows Retry with Mid + Skip", () => {
    const onRetry = vi.fn();
    const onSkip = vi.fn();
    render(
      <SpecCard
        spec={baseSpec}
        state="error"
        errorMessage="quota exceeded"
        onRetryCheaper={onRetry}
        onSkip={onSkip}
      />,
    );
    expect(screen.getByText(/Render failed/)).toBeInTheDocument();
    expect(screen.getByText("quota exceeded")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Retry with Mid"));
    fireEvent.click(screen.getByText("Skip"));
    expect(onRetry).toHaveBeenCalled();
    expect(onSkip).toHaveBeenCalled();
  });

  it("refining state submits the typed note via onRefine", () => {
    const onRefine = vi.fn();
    render(
      <SpecCard
        spec={baseSpec}
        state="refining"
        render={sampleRender}
        onRefine={onRefine}
      />,
    );
    const input = screen.getByLabelText(/Refine spec_1/i);
    fireEvent.change(input, { target: { value: "softer light" } });
    fireEvent.click(screen.getByText("Apply"));
    expect(onRefine).toHaveBeenCalledWith("softer light");
  });
});
