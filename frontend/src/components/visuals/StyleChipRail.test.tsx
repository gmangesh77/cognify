import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import { StyleChipRail } from "./StyleChipRail";
import type { StyleCatalogueEntry } from "@/types/visuals";

const styles: StyleCatalogueEntry[] = [
  {
    key: "lifestyle_photo",
    label: "Lifestyle Photo",
    category: "photo",
    default_aspect: "16:9",
    short_desc: "Editorial DSLR.",
    prompt_fragment: "frag",
  },
  {
    key: "isometric_3d",
    label: "Isometric 3D",
    category: "illustration",
    default_aspect: "4:3",
    short_desc: "Isometric.",
    prompt_fragment: "frag",
  },
  {
    key: "editorial",
    label: "Editorial",
    category: "editorial",
    default_aspect: "16:9",
    short_desc: "Editorial.",
    prompt_fragment: "frag",
  },
];

describe("StyleChipRail", () => {
  it("renders one chip per supplied style", () => {
    render(<StyleChipRail styles={styles} selected={null} onSelect={() => {}} />);
    expect(screen.getByText("Lifestyle Photo")).toBeInTheDocument();
    expect(screen.getByText("Isometric 3D")).toBeInTheDocument();
    expect(screen.getByText("Editorial")).toBeInTheDocument();
  });

  it("marks the selected chip with aria-checked=true", () => {
    render(
      <StyleChipRail
        styles={styles}
        selected="isometric_3d"
        onSelect={() => {}}
      />,
    );
    expect(screen.getByText("Isometric 3D")).toHaveAttribute(
      "aria-checked",
      "true",
    );
    expect(screen.getByText("Lifestyle Photo")).toHaveAttribute(
      "aria-checked",
      "false",
    );
  });

  it("emits the key when an unselected chip is clicked", () => {
    const onSelect = vi.fn();
    render(
      <StyleChipRail
        styles={styles}
        selected={null}
        onSelect={onSelect}
      />,
    );
    fireEvent.click(screen.getByText("Lifestyle Photo"));
    expect(onSelect).toHaveBeenCalledWith("lifestyle_photo");
  });

  it("emits null when the already-selected chip is clicked (toggle off)", () => {
    const onSelect = vi.fn();
    render(
      <StyleChipRail
        styles={styles}
        selected="lifestyle_photo"
        onSelect={onSelect}
      />,
    );
    fireEvent.click(screen.getByText("Lifestyle Photo"));
    expect(onSelect).toHaveBeenCalledWith(null);
  });

  it("renders a +N overflow indicator when more chips exist than visibleLimit", () => {
    render(
      <StyleChipRail
        styles={styles}
        selected={null}
        onSelect={() => {}}
        visibleLimit={2}
      />,
    );
    expect(screen.getByText("+1 more")).toBeInTheDocument();
  });
});
