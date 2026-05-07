import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

vi.mock("@/lib/api/visuals", () => ({
  fetchSavedAssets: vi.fn(),
}));

import { fetchSavedAssets } from "@/lib/api/visuals";
import { SavedAssetGallery } from "./SavedAssetGallery";

const sampleResponse = {
  items: [
    {
      spec_id: "hero1",
      article_id: "a1",
      article_title: "Quiet refactor",
      image_url: "https://cdn.test/a1/hero1.png",
      role_style: "hero",
      visual_style: "lifestyle_photo",
      aspect_ratio: "16:9",
      provider: "gemini_flash",
      cost_usd: 0.001,
      generated_at: "2026-05-07T00:00:00+00:00",
      alt_text: "alt",
      caption: "cap",
    },
    {
      spec_id: "card1",
      article_id: "a2",
      article_title: "Other article",
      image_url: "https://cdn.test/a2/card1.png",
      role_style: "feature_card",
      visual_style: "isometric_3d",
      aspect_ratio: "4:3",
      provider: "imagen_4",
      cost_usd: 0.04,
      generated_at: "2026-05-06T00:00:00+00:00",
      alt_text: null,
      caption: null,
    },
  ],
  facets: {
    by_article: { "Quiet refactor": 1, "Other article": 1 },
    by_provider: { gemini_flash: 1, imagen_4: 1 },
    by_role_style: { hero: 1, feature_card: 1 },
  },
  total_count: 2,
  total_spend_usd: 0.041,
};

describe("SavedAssetGallery", () => {
  beforeEach(() => {
    vi.mocked(fetchSavedAssets).mockReset();
    vi.mocked(fetchSavedAssets).mockResolvedValue(sampleResponse);
  });

  it("renders nothing when closed", () => {
    render(<SavedAssetGallery open={false} onClose={() => {}} />);
    expect(screen.queryByTestId("saved-asset-gallery-modal")).not.toBeInTheDocument();
  });

  it("loads + renders items when opened", async () => {
    render(<SavedAssetGallery open onClose={() => {}} />);
    await waitFor(() => {
      expect(fetchSavedAssets).toHaveBeenCalled();
    });
    await waitFor(() => {
      expect(screen.getAllByText(/Quiet refactor/).length).toBeGreaterThan(0);
    });
    expect(screen.getAllByText(/Other article/).length).toBeGreaterThan(0);
  });

  it("shows the total count and spend in the header", async () => {
    render(<SavedAssetGallery open onClose={() => {}} />);
    await waitFor(() => {
      expect(screen.getByText(/2 images · \$0\.04 spent/)).toBeInTheDocument();
    });
  });

  it("calls onSelect with the asset when a card is clicked", async () => {
    const onSelect = vi.fn();
    render(<SavedAssetGallery open onClose={() => {}} onSelect={onSelect} />);
    await waitFor(() => {
      expect(screen.getAllByText(/Quiet refactor/).length).toBeGreaterThan(0);
    });
    // The grid renders <ul role="list"> with one <li> per asset; pick the first
    // card button to dispatch the select. Facet entries are buttons too but
    // they're inside the sidebar — we want the grid card.
    const cardButtons = screen.getAllByRole("button");
    const heroCardButton = cardButtons.find((btn) =>
      btn.textContent?.includes("Quiet refactor") &&
      btn.textContent?.includes("Hero"),
    );
    expect(heroCardButton).toBeDefined();
    fireEvent.click(heroCardButton!);
    expect(onSelect).toHaveBeenCalledWith(
      expect.objectContaining({ spec_id: "hero1" }),
    );
  });

  it("re-fetches with role_style filter when a role chip is clicked", async () => {
    render(<SavedAssetGallery open onClose={() => {}} />);
    await waitFor(() => {
      expect(fetchSavedAssets).toHaveBeenCalledWith({});
    });
    fireEvent.click(screen.getByRole("button", { name: /^Hero$/ }));
    await waitFor(() => {
      expect(fetchSavedAssets).toHaveBeenLastCalledWith(
        expect.objectContaining({ role_style: "hero" }),
      );
    });
  });

  it("renders an empty state when no items are returned", async () => {
    vi.mocked(fetchSavedAssets).mockResolvedValueOnce({
      ...sampleResponse,
      items: [],
      total_count: 0,
    });
    render(<SavedAssetGallery open onClose={() => {}} />);
    await waitFor(() => {
      expect(screen.getByText(/No saved visuals yet/)).toBeInTheDocument();
    });
  });

  it("emits onClose when the close button is clicked", async () => {
    const onClose = vi.fn();
    render(<SavedAssetGallery open onClose={onClose} />);
    await waitFor(() => {
      expect(screen.getAllByText(/Quiet refactor/).length).toBeGreaterThan(0);
    });
    fireEvent.click(screen.getByLabelText(/Close gallery/));
    expect(onClose).toHaveBeenCalled();
  });
});
