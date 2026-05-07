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
