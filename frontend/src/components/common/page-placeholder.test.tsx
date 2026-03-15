import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { PagePlaceholder } from "./page-placeholder";
import { Compass } from "lucide-react";

describe("PagePlaceholder", () => {
  it("renders title and coming soon message", () => {
    render(<PagePlaceholder title="Topic Discovery" icon={Compass} />);
    expect(screen.getByText("Topic Discovery")).toBeInTheDocument();
    expect(screen.getByText("Coming Soon")).toBeInTheDocument();
  });
});
