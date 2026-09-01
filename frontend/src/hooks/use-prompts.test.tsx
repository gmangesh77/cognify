import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { usePrompts } from "./use-prompts";
import * as api from "@/lib/api/prompts";

vi.mock("@/lib/api/prompts");

const view = {
  key: "content_outline.user",
  step: "content_outline",
  description: "d",
  variables: ["title"],
  default_template: "D",
  template: "D",
  is_overridden: false,
  updated_by: null,
  updated_at: null,
};

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe("usePrompts", () => {
  beforeEach(() => {
    vi.mocked(api.listPrompts).mockResolvedValue([view]);
    vi.mocked(api.updatePrompt).mockResolvedValue({ ...view, template: "X", is_overridden: true });
    vi.mocked(api.resetPrompt).mockResolvedValue(view);
  });

  it("loads prompts and refetches after save and reset", async () => {
    const { result } = renderHook(() => usePrompts(), { wrapper });
    await waitFor(() => expect(result.current.prompts).toHaveLength(1));
    await act(() => result.current.save("content_outline.user", "X"));
    expect(api.updatePrompt).toHaveBeenCalledWith("content_outline.user", "X");
    await act(() => result.current.reset("content_outline.user"));
    expect(api.resetPrompt).toHaveBeenCalledWith("content_outline.user");
    expect(api.listPrompts).toHaveBeenCalledTimes(3);
  });
});
