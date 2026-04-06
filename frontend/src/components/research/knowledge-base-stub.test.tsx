import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { KnowledgeBaseStub } from "./knowledge-base-stub";

vi.mock("@/lib/api/metrics", () => ({
  fetchKnowledgeBaseStats: vi.fn().mockResolvedValue({
    total_sessions: 5,
    total_sources: 42,
    total_embeddings: 128,
  }),
}));

function renderWithQuery(ui: React.ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>{ui}</QueryClientProvider>,
  );
}

describe("KnowledgeBaseStub", () => {
  it("renders session count from API", async () => {
    renderWithQuery(<KnowledgeBaseStub />);
    expect(await screen.findByText("5")).toBeInTheDocument();
    expect(screen.getByText("Sessions")).toBeInTheDocument();
  });

  it("renders total sources from API", async () => {
    renderWithQuery(<KnowledgeBaseStub />);
    expect(await screen.findByText("42")).toBeInTheDocument();
    expect(screen.getByText("Sources")).toBeInTheDocument();
  });

  it("renders total embeddings from API", async () => {
    renderWithQuery(<KnowledgeBaseStub />);
    expect(await screen.findByText("128")).toBeInTheDocument();
    expect(screen.getByText("Embeddings")).toBeInTheDocument();
  });
});
