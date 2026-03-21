import { render, screen } from "@testing-library/react";
import { KnowledgeBaseStub } from "./knowledge-base-stub";

describe("KnowledgeBaseStub", () => {
  it("renders placeholder text", () => {
    render(<KnowledgeBaseStub />);
    expect(screen.getByText("Knowledge Base")).toBeInTheDocument();
    expect(screen.getByText(/coming in a future update/)).toBeInTheDocument();
  });
});
