import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

vi.mock("@/lib/api/visuals", () => ({
  fetchVisualStyles: vi.fn(),
  planVisuals: vi.fn(),
  renderSpec: vi.fn(),
}));

import {
  fetchVisualStyles,
  planVisuals,
  renderSpec,
} from "@/lib/api/visuals";
import { resetVisualStylesCache } from "@/lib/visuals/visualStyles";
import { VisualStudio } from "./VisualStudio";

const stylesResponse = {
  styles: [
    {
      key: "lifestyle_photo",
      label: "Lifestyle Photo",
      category: "photo" as const,
      default_aspect: "16:9" as const,
      short_desc: "DSLR.",
      prompt_fragment: "frag",
    },
    {
      key: "isometric_3d",
      label: "Isometric 3D",
      category: "illustration" as const,
      default_aspect: "4:3" as const,
      short_desc: "Iso.",
      prompt_fragment: "frag",
    },
  ],
  role_defaults: { hero: "lifestyle_photo" },
  personas: [{ key: "general_business", direction: "Calm." }],
  default_persona: "general_business",
  banned_cliches_block: "BANNED CLICHES",
  planner_catalogue_block: "Available visual styles:",
};

const planResponse = {
  cover: {
    id: "cover",
    role_style: "hero" as const,
    visual_style: "lifestyle_photo",
    prompt: "Founder portrait.",
    alt_text: "Founder",
    aspect_ratio: "16:9" as const,
    placement: {
      anchor: "cover" as const,
      heading_text: null,
      paragraph_index: null,
      section_index: -1,
    },
    rationale: "Anchors the article identity.",
    provider: null,
  },
  section_specs: [],
};

const article = {
  topic: {
    title: "Quiet refactor",
    description: "Steady cleanups beat rewrites.",
    domain: "engineering",
  },
  summary: "Small steps compound.",
};

describe("VisualStudio", () => {
  beforeEach(() => {
    resetVisualStylesCache();
    vi.mocked(fetchVisualStyles).mockResolvedValue(stylesResponse);
    vi.mocked(planVisuals).mockReset();
    vi.mocked(renderSpec).mockReset();
  });

  afterEach(() => {
    resetVisualStylesCache();
  });

  it("renders the panel header + Plan visuals CTA", async () => {
    render(<VisualStudio article={article} />);
    expect(screen.getByTestId("visual-studio-panel")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /^Plan visuals$/ }),
    ).toBeInTheDocument();
    await waitFor(() => {
      expect(fetchVisualStyles).toHaveBeenCalled();
    });
  });

  it("calls planVisuals with topic context when Plan visuals is clicked", async () => {
    vi.mocked(planVisuals).mockResolvedValue(planResponse);
    render(<VisualStudio article={article} />);
    fireEvent.click(screen.getByRole("button", { name: /^Plan visuals$/ }));
    await waitFor(() => {
      expect(planVisuals).toHaveBeenCalledWith(
        expect.objectContaining({
          topic: article.topic,
          article_summary: article.summary,
          plan_cover: true,
        }),
      );
    });
  });

  it("renders the planned cover spec after a successful plan call", async () => {
    vi.mocked(planVisuals).mockResolvedValue(planResponse);
    render(<VisualStudio article={article} />);
    fireEvent.click(screen.getByRole("button", { name: /^Plan visuals$/ }));
    await waitFor(() => {
      expect(screen.getByText(/Spec list/)).toBeInTheDocument();
    });
    expect(screen.getByText(/hero/)).toBeInTheDocument();
  });

  it("renders an error message when planVisuals rejects", async () => {
    vi.mocked(planVisuals).mockRejectedValue(new Error("boom"));
    render(<VisualStudio article={article} />);
    fireEvent.click(screen.getByRole("button", { name: /^Plan visuals$/ }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("boom");
  });
});
