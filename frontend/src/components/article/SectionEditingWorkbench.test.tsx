import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { SectionEditingWorkbench, type ActiveSection } from "./SectionEditingWorkbench";

vi.mock("./InlineProseEditor", () => ({
  InlineProseEditor: ({ initialMarkdown }: { initialMarkdown: string }) => (
    <div data-testid="inline-editor" data-md={initialMarkdown} />
  ),
}));
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

function Harness(props: { onToast: (m: string) => void; onPersisted: () => void }) {
  const [section, setSection] = useState<ActiveSection | null>(SECTION);
  return section ? (
    <SectionEditingWorkbench
      articleId="art-1"
      section={section}
      defaultPersona={null}
      initialPanel={null}
      onChange={setSection}
      onOpenHistory={vi.fn()}
      {...props}
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

  it("toggles the regenerate panel and opens history for the section id", () => {
    render(<Harness onToast={vi.fn()} onPersisted={vi.fn()} />);
    fireEvent.click(screen.getByTestId("open-regenerate-panel"));
    expect(screen.getByTestId("accept-regen")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("open-regenerate-panel"));
    expect(screen.queryByTestId("accept-regen")).toBeNull();
  });
});
