import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import {
  SectionEditingWorkbench,
  type ActiveSection,
  type WorkbenchPanel,
} from "./SectionEditingWorkbench";

vi.mock("./InlineProseEditor", async () => {
  const React = await import("react");
  // Stateful stand-in: like the real editor it seeds its draft ONCE, so a
  // remount (not a re-render) is what would lose unsaved text.
  const InlineProseEditor = ({ initialMarkdown }: { initialMarkdown: string }) => {
    const [draft, setDraft] = React.useState(initialMarkdown);
    return (
      <textarea
        data-testid="inline-editor"
        data-md={initialMarkdown}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
      />
    );
  };
  return { InlineProseEditor };
});
vi.mock("./AIRewritePopover", () => ({
  AIRewritePopover: ({ onAccept }: { onAccept: (md: string, instr: string) => void }) => (
    <button type="button" data-testid="stage-rewrite" onClick={() => onAccept("## A\n\nrewritten", "x")}>
      stage
    </button>
  ),
}));
vi.mock("./HumanizationDiffPanel", () => ({ HumanizationDiffPanel: () => <div /> }));
vi.mock("@/components/visuals/SectionHtmlRefinePanel", () => ({ SectionHtmlRefinePanel: () => <div /> }));
vi.mock("./RegeneratePopover", () => ({
  RegeneratePopover: ({ onAccepted }: { onAccepted: (md: string, vid: string) => void }) => (
    <button type="button" data-testid="accept-regen" onClick={() => onAccepted("## A\n\nregen", "v-12345678")}>
      accept
    </button>
  ),
}));

const SECTION: ActiveSection = { index: 0, sectionId: "art-1:0", markdown: "## A\n\noriginal" };

function Harness(props: {
  onToast: (m: string) => void;
  onPersisted: () => void;
  panel?: WorkbenchPanel | null;
  onPanelChange?: (next: WorkbenchPanel | null) => void;
}) {
  const [section, setSection] = useState<ActiveSection | null>(SECTION);
  const [ownPanel, setOwnPanel] = useState<WorkbenchPanel | null>(null);
  const { panel, onPanelChange, ...rest } = props;
  return section ? (
    <SectionEditingWorkbench
      articleId="art-1"
      section={section}
      defaultPersona={null}
      panel={panel === undefined ? ownPanel : panel}
      onPanelChange={onPanelChange ?? setOwnPanel}
      onChange={setSection}
      onOpenHistory={vi.fn()}
      {...rest}
    />
  ) : (
    <p data-testid="closed">closed</p>
  );
}

describe("SectionEditingWorkbench", () => {
  it("accepting a regenerate clears a previously staged rewrite", () => {
    const onToast = vi.fn();
    const onPersisted = vi.fn();
    render(<Harness onToast={onToast} onPersisted={onPersisted} />);

    fireEvent.click(screen.getByText("Rewrite with AI"));
    fireEvent.click(screen.getByTestId("stage-rewrite"));
    expect(screen.getByTestId("inline-editor")).toHaveAttribute("data-md", "## A\n\nrewritten");

    fireEvent.click(screen.getByTestId("open-regenerate-panel"));
    fireEvent.click(screen.getByTestId("accept-regen"));

    expect(screen.getByTestId("closed")).toBeInTheDocument();
    expect(screen.queryByTestId("inline-editor")).toBeNull();
    expect(onPersisted).toHaveBeenCalledTimes(1);
    expect(onToast).toHaveBeenCalledWith("Section regenerated (version v-123456)");
  });

  it("switching the controlled panel keeps the editor mounted (draft survives)", () => {
    const onPanelChange = vi.fn();
    const { rerender } = render(
      <Harness onToast={vi.fn()} onPersisted={vi.fn()} panel={null} onPanelChange={onPanelChange} />,
    );
    const textarea = screen.getByRole("textbox") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: "## A\n\nedited but unsaved" } });
    rerender(
      <Harness onToast={vi.fn()} onPersisted={vi.fn()} panel="refine" onPanelChange={onPanelChange} />,
    );
    expect((screen.getByRole("textbox") as HTMLTextAreaElement).value).toBe(
      "## A\n\nedited but unsaved",
    );
    expect(screen.getByText("Hide refine")).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(screen.getByText("Hide refine"));
    expect(onPanelChange).toHaveBeenLastCalledWith(null);
  });

  it("toggles the regenerate panel and opens history for the section id", () => {
    render(<Harness onToast={vi.fn()} onPersisted={vi.fn()} />);
    fireEvent.click(screen.getByTestId("open-regenerate-panel"));
    expect(screen.getByTestId("accept-regen")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("open-regenerate-panel"));
    expect(screen.queryByTestId("accept-regen")).toBeNull();
  });
});
