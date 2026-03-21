import { describe, it, expect } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import ResearchPage from "./page";

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

describe("ResearchPage", () => {
  it("renders header", async () => {
    render(<ResearchPage />, { wrapper: createWrapper() });
    expect(screen.getByText("Research Sessions")).toBeInTheDocument();
  });

  it("renders filter tabs", async () => {
    render(<ResearchPage />, { wrapper: createWrapper() });
    await waitFor(() => expect(screen.getByText("All")).toBeInTheDocument());
    expect(screen.getByText("Complete")).toBeInTheDocument();
    expect(screen.getByText("Failed")).toBeInTheDocument();
  });

  it("renders session cards from mock data", async () => {
    render(<ResearchPage />, { wrapper: createWrapper() });
    await waitFor(() => expect(screen.getByText("AI Security Trends 2026")).toBeInTheDocument());
    expect(screen.getByText("Zero Trust Architecture")).toBeInTheDocument();
  });

  it("filters sessions by status tab", async () => {
    render(<ResearchPage />, { wrapper: createWrapper() });
    await waitFor(() => expect(screen.getByText("AI Security Trends 2026")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Failed" }));
    await waitFor(() => {
      expect(screen.getByText("Quantum Computing Risks")).toBeInTheDocument();
      expect(screen.queryByText("AI Security Trends 2026")).not.toBeInTheDocument();
    });
  });

  it("expands card to show agent steps", async () => {
    render(<ResearchPage />, { wrapper: createWrapper() });
    await waitFor(() => expect(screen.getByText("AI Security Trends 2026")).toBeInTheDocument());
    fireEvent.click(screen.getByText("AI Security Trends 2026"));
    await waitFor(() => expect(screen.getByText("Plan Research")).toBeInTheDocument());
  });

  it("collapses expanded card on second click", async () => {
    render(<ResearchPage />, { wrapper: createWrapper() });
    await waitFor(() => expect(screen.getByText("AI Security Trends 2026")).toBeInTheDocument());
    fireEvent.click(screen.getByText("AI Security Trends 2026"));
    await waitFor(() => expect(screen.getByText("Plan Research")).toBeInTheDocument());
    fireEvent.click(screen.getByText("AI Security Trends 2026"));
    await waitFor(() => expect(screen.queryByText("Plan Research")).not.toBeInTheDocument());
  });

  it("renders knowledge base stub", async () => {
    render(<ResearchPage />, { wrapper: createWrapper() });
    await waitFor(() => expect(screen.getByText("Knowledge Base")).toBeInTheDocument());
  });
});
