import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SectionContextToolbar } from "./SectionContextToolbar";

describe("SectionContextToolbar", () => {
  function setup({ visible }: { visible: boolean }) {
    const onEditText = vi.fn();
    const onEditVisual = vi.fn();
    const onRefineLayout = vi.fn();
    render(
      <SectionContextToolbar
        sectionId="abc:1"
        sectionIndex={1}
        visible={visible}
        onEditText={onEditText}
        onEditVisual={onEditVisual}
        onRefineLayout={onRefineLayout}
      />,
    );
    return { onEditText, onEditVisual, onRefineLayout };
  }

  it("renders dimmed-but-present when not hovered (affordance)", () => {
    setup({ visible: false });
    const toolbar = screen.getByRole("toolbar");
    expect(toolbar).toBeInTheDocument();
    expect(toolbar.className).toMatch(/opacity-30/);
  });

  it("renders all three actions when visible", () => {
    setup({ visible: true });
    expect(screen.getByTestId("toolbar-edit-text-1")).toBeInTheDocument();
    expect(screen.getByTestId("toolbar-edit-visual-1")).toBeInTheDocument();
    expect(screen.getByTestId("toolbar-refine-layout-1")).toBeInTheDocument();
    expect(screen.getByRole("toolbar").className).toMatch(/opacity-100/);
  });

  it("fires the right callback when each button is clicked", () => {
    const { onEditText, onEditVisual, onRefineLayout } = setup({
      visible: true,
    });
    fireEvent.click(screen.getByTestId("toolbar-edit-text-1"));
    fireEvent.click(screen.getByTestId("toolbar-edit-visual-1"));
    fireEvent.click(screen.getByTestId("toolbar-refine-layout-1"));
    expect(onEditText).toHaveBeenCalledTimes(1);
    expect(onEditVisual).toHaveBeenCalledTimes(1);
    expect(onRefineLayout).toHaveBeenCalledTimes(1);
  });
});
