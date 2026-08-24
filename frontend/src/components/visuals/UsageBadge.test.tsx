import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import { UsageBadge } from "./UsageBadge";

describe("UsageBadge", () => {
  it("renders the formatted total in the compact pill", () => {
    render(<UsageBadge totalUsd={0.0432} />);
    expect(screen.getByRole("button")).toHaveTextContent("$0.043 this article");
  });

  it("expands to show the breakdown on click", () => {
    render(
      <UsageBadge
        totalUsd={0.06}
        breakdown={[
          { provider: "gemini_flash", count: 3, usd: 0.003 },
          { provider: "imagen_4", count: 1, usd: 0.04 },
        ]}
      />,
    );
    fireEvent.click(screen.getByRole("button"));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("gemini_flash")).toBeInTheDocument();
    expect(screen.getByText("imagen_4")).toBeInTheDocument();
  });

  it("flips to the warning treatment when within 20% of the cap", () => {
    render(<UsageBadge totalUsd={8.5} budgetUsd={10} />);
    const pill = screen.getByRole("button");
    expect(pill.className).toContain("error");
  });

  it("forceWarning renders the warning regardless of total", () => {
    render(<UsageBadge totalUsd={0} forceWarning />);
    const pill = screen.getByRole("button");
    expect(pill.className).toContain("error");
  });
});

describe("UsageBadge extended display (AUTHOR-005)", () => {
  it("renders a custom label", () => {
    render(<UsageBadge totalUsd={0.05} label="this session" />);
    expect(screen.getByRole("button")).toHaveTextContent("$0.050 this session");
  });

  it("renders tokens and images segments when provided", () => {
    render(<UsageBadge totalUsd={0.052} tokens={3200} images={2} />);
    expect(screen.getByRole("button")).toHaveTextContent(
      "$0.052 this article · 3.2k tok · 2 img",
    );
  });

  it("omits tokens segment when tokens is null and images is zero", () => {
    render(<UsageBadge totalUsd={0.05} tokens={null} images={0} />);
    const pill = screen.getByRole("button");
    expect(pill).toHaveTextContent("$0.050 this article");
    expect(pill).not.toHaveTextContent("tok");
    expect(pill).not.toHaveTextContent("img");
  });

  it("keeps the legacy call signature working", () => {
    render(<UsageBadge totalUsd={0.1} />);
    expect(screen.getByRole("button")).toHaveTextContent("$0.100 this article");
  });
});
