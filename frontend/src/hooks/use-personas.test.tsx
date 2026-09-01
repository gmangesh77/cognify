import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { usePersona, usePersonas } from "./use-personas";
import * as api from "@/lib/api/personas";

vi.mock("@/lib/api/personas");

const summary = {
  id: "p1",
  name: "House Style",
  description: null,
  sample_count: 5,
  ready: true,
  updated_at: "2026-09-01T00:00:00Z",
};

const detail = {
  ...summary,
  fingerprint: { dims: {}, sample_count: 5 },
  samples: [{ id: "s1", word_count: 200, preview: "prose…", created_at: "2026-09-01T00:00:00Z" }],
};

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe("usePersonas", () => {
  beforeEach(() => {
    vi.mocked(api.listPersonas).mockResolvedValue([summary]);
    vi.mocked(api.createPersona).mockResolvedValue(summary);
    vi.mocked(api.updatePersona).mockResolvedValue({ ...summary, name: "New Name" });
    vi.mocked(api.deletePersona).mockResolvedValue(undefined);
  });

  it("loads personas and refetches after create, update, remove", async () => {
    const { result } = renderHook(() => usePersonas(), { wrapper });
    await waitFor(() => expect(result.current.personas).toHaveLength(1));

    await act(() => result.current.create({ name: "House Style" }));
    expect(api.createPersona).toHaveBeenCalledWith({ name: "House Style" });

    await act(() => result.current.update("p1", { name: "New Name" }));
    expect(api.updatePersona).toHaveBeenCalledWith("p1", { name: "New Name" });

    await act(() => result.current.remove("p1"));
    expect(api.deletePersona).toHaveBeenCalledWith("p1");

    expect(api.listPersonas).toHaveBeenCalledTimes(4);
  });
});

describe("usePersona", () => {
  beforeEach(() => {
    vi.mocked(api.getPersona).mockResolvedValue(detail);
    vi.mocked(api.addSample).mockResolvedValue(detail);
    vi.mocked(api.deleteSample).mockResolvedValue(detail);
  });

  it("does not fetch when id is null", () => {
    renderHook(() => usePersona(null), { wrapper });
    expect(api.getPersona).not.toHaveBeenCalled();
  });

  it("loads the persona and refetches after addSample and removeSample", async () => {
    const { result } = renderHook(() => usePersona("p1"), { wrapper });
    await waitFor(() => expect(result.current.persona).toEqual(detail));

    await act(() => result.current.addSample("Some long sample text."));
    expect(api.addSample).toHaveBeenCalledWith("p1", "Some long sample text.");

    await act(() => result.current.removeSample("s1"));
    expect(api.deleteSample).toHaveBeenCalledWith("p1", "s1");

    expect(api.getPersona).toHaveBeenCalledTimes(3);
  });
});
